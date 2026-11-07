<?php
/** Authenticated HTTP integration against the disposable Apache container only. */
$_SERVER['HTTP_HOST'] = 'inframarinos-wp';
$_SERVER['SERVER_NAME'] = 'inframarinos-wp';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SERVER_PROTOCOL'] = 'HTTP/1.1';
require '/var/www/html/wp-load.php';
if ( 'http://inframarinos-wp' !== home_url() ) {
    throw new RuntimeException( 'Refusing to run outside isolated QA.' );
}
$checks = 0;
function http_expect( $condition, $message ) {
    global $checks;
    if ( ! $condition ) {
        throw new RuntimeException( $message );
    }
    ++$checks;
}
function http_login( $user ) {
    $expiration = time() + 3600;
    $token = WP_Session_Tokens::get_instance( $user->ID )->create( $expiration );
    $logged = wp_generate_auth_cookie( $user->ID, $expiration, 'logged_in', $token );
    $_COOKIE[ LOGGED_IN_COOKIE ] = $logged;
    wp_set_current_user( $user->ID );
    return AUTH_COOKIE . '=' . wp_generate_auth_cookie( $user->ID, $expiration, 'auth', $token ) . '; ' . LOGGED_IN_COOKIE . '=' . $logged;
}
function http_request( $path, $cookies = '', $data = null, $headers = array(), $multipart = false ) {
    $ch = curl_init( 'http://127.0.0.1' . $path );
    curl_setopt_array( $ch, array( CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 30, CURLOPT_HTTPHEADER => array_merge( array( 'Host: inframarinos-wp' ), $headers ), CURLOPT_COOKIE => $cookies, CURLOPT_HEADER => false ) );
    if ( null !== $data ) {
        curl_setopt( $ch, CURLOPT_POST, true );
        curl_setopt( $ch, CURLOPT_POSTFIELDS, $multipart ? $data : http_build_query( $data ) );
    }
    $body = curl_exec( $ch );
    if ( false === $body ) {
        throw new RuntimeException( curl_error( $ch ) );
    }
    $code = curl_getinfo( $ch, CURLINFO_RESPONSE_CODE );
    curl_close( $ch );
    return array( $code, $body );
}
$manager = get_user_by( 'login', 'infra-manager-test' );
$cookie = http_login( $manager );
list( $code, $body ) = http_request( '/wp-admin/admin.php?page=inframarinos', $cookie );
http_expect( 200 === $code && false !== strpos( $body, 'Guardar cambios de la web' ), 'Manager cannot open management panel: HTTP ' . $code . ' ' . substr( trim( preg_replace( '/\s+/', ' ', strip_tags( preg_replace( '#<(style|script)[^>]*>.*?</\\1>#s', '', $body ) ) ) ), 0, 450 ) );
http_expect( false !== strpos( $body, 'inframarinos-gestion/admin.js' ), 'Media and schedule controls are not enqueued.' );
list( $code ) = http_request( '/wp-content/plugins/inframarinos-gestion/admin.js', $cookie );
http_expect( 200 === $code, 'Management JavaScript asset is unavailable.' );

$upload = array( 'action' => 'upload-attachment', '_wpnonce' => wp_create_nonce( 'media-form' ), 'name' => 'foto-cliente.jpg', 'async-upload' => new CURLFile( get_theme_file_path( '/assets/bar.jpg' ), 'image/jpeg', 'foto-cliente.jpg' ) );
list( $code, $body ) = http_request( '/wp-admin/async-upload.php', $cookie, $upload, array(), true );
$image = json_decode( $body, true );
http_expect( 200 === $code && ! empty( $image['success'] ) && ! empty( $image['data']['id'] ), 'Manager image upload failed.' );
$attachment = $image['data']['id'];

$settings = inframarinos_get_settings();
$settings['instagram_handle'] = 'gestion.real';
$settings['hero_image'] = $attachment;
$settings['notice_enabled'] = '1';
$settings['notice_text'] = 'Aviso guardado desde el panel real.';
$settings['hours'] = array( array( 'days' => 'Sábados', 'time' => '12:00 — 23:30' ) );
$payload = array( 'option_page' => 'inframarinos', 'action' => 'update', '_wpnonce' => wp_create_nonce( 'inframarinos-options' ), '_wp_http_referer' => '/wp-admin/admin.php?page=inframarinos', 'inframarinos_settings' => $settings );
list( $code, $body ) = http_request( '/wp-admin/options.php', $cookie, $payload );
http_expect( 302 === $code, 'Manager cannot save through the native WordPress settings endpoint.' );
wp_cache_flush();
$saved = inframarinos_get_settings();
http_expect( $saved['instagram_handle'] === 'gestion.real' && $saved['hero_image'] === (int) $attachment, 'Changes from native form were not stored.' );
list( $code, $body ) = http_request( '/' );
http_expect( 200 === $code && false !== strpos( $body, 'instagram.com/gestion.real/' ) && false !== strpos( $body, 'Aviso guardado desde el panel real.' ), 'Live frontend does not show manager edits.' );
http_expect( false !== strpos( $body, '/uploads/' ) && false !== strpos( $body, 'Sábados' ), 'Uploaded photo or schedule missing from frontend.' );
http_expect( false !== strpos( $body, 'window.inframarinosData' ) && false !== strpos( $body, 'assets/site.js' ), 'Live frontend assets or dynamic tapa data missing.' );
file_put_contents( '/tmp/inframarinos-http.html', $body );
$payload['_wpnonce'] = 'invalid-nonce';
$payload['inframarinos_settings']['instagram_handle'] = 'should.not.save';
list( $code ) = http_request( '/wp-admin/options.php', $cookie, $payload );
http_expect( 403 === $code, 'Settings update without valid nonce was not rejected.' );

$dish = get_posts( array( 'post_type' => 'infra_plato', 'numberposts' => 1, 'post_status' => 'publish' ) )[0];
$dish_payload = array( 'action' => 'editpost', 'originalaction' => 'editpost', 'post_ID' => $dish->ID, 'post_type' => 'infra_plato', '_wpnonce' => wp_create_nonce( 'update-post_' . $dish->ID ), 'post_title' => 'Producto editado desde WordPress', 'content' => 'Descripción editada por el encargado.', 'post_status' => 'publish', 'original_post_status' => 'publish', 'menu_order' => 7, 'inframarinos_dish_nonce' => wp_create_nonce( 'inframarinos_dish' ), 'infra_price' => '12,75', 'infra_available' => '1', 'infra_tapa' => '1' );
list( $code, $body ) = http_request( '/wp-admin/post.php', $cookie, $dish_payload );
http_expect( 302 === $code, 'Manager cannot save a product using the native editor endpoint.' );
wp_cache_flush();
http_expect( get_post( $dish->ID )->post_title === 'Producto editado desde WordPress' && get_post_meta( $dish->ID, '_infra_price', true ) === '12.75' && (int) get_post( $dish->ID )->menu_order === 7, 'Product editor did not save title, price and order.' );

$subscriber = get_user_by( 'login', 'infra-subscriber-test' );
if ( ! $subscriber ) {
    $id = wp_insert_user( array( 'user_login' => 'infra-subscriber-test', 'user_pass' => wp_generate_password( 40, true, true ), 'role' => 'subscriber' ) );
    $subscriber = get_user_by( 'id', $id );
}
$sub_cookie = http_login( $subscriber );
list( $code ) = http_request( '/wp-admin/admin.php?page=inframarinos', $sub_cookie );
http_expect( 403 === $code, 'Subscriber can access bar settings.' );
$payload['_wpnonce'] = wp_create_nonce( 'inframarinos-options' );
list( $code ) = http_request( '/wp-admin/options.php', $sub_cookie, $payload );
http_expect( 403 === $code, 'Subscriber can save bar settings.' );
wp_cache_flush();
http_expect( inframarinos_get_settings()['instagram_handle'] === 'gestion.real', 'Rejected requests modified settings.' );
wp_set_current_user( get_user_by( 'login', 'infra-admin-test' )->ID );
update_option( 'inframarinos_settings', inframarinos_defaults() );
wp_delete_attachment( $attachment, true );
echo "PASS: $checks authenticated HTTP assertions, including image upload, real form saves and access restrictions.\n";
