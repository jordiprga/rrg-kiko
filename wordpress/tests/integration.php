<?php
/** Run only in a disposable database: changes products and settings. */
$_SERVER['HTTP_HOST'] = 'inframarinos-wp';
$_SERVER['SERVER_NAME'] = 'inframarinos-wp';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SERVER_PROTOCOL'] = 'HTTP/1.1';
require '/var/www/html/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
require_once ABSPATH . 'wp-admin/includes/template.php';
if ( 'http://inframarinos-wp' !== home_url() ) {
    throw new RuntimeException( 'Refusing to run outside the isolated test site.' );
}
$checks = 0;
function infra_expect( $condition, $message ) {
    global $checks;
    if ( ! $condition ) {
        throw new RuntimeException( $message );
    }
    ++$checks;
}
function infra_render() {
    ob_start();
    include get_theme_file_path( '/front-page.php' );
    return ob_get_clean();
}
wp_set_current_user( get_user_by( 'login', 'infra-admin-test' )->ID );
foreach ( get_posts( array( 'post_type' => 'infra_plato', 'post_status' => array( 'publish', 'draft', 'pending', 'private', 'future', 'trash' ), 'numberposts' => -1, 'fields' => 'ids' ) ) as $old_post ) {
    wp_delete_post( $old_post, true );
}
update_option( 'inframarinos_settings', inframarinos_defaults() );
infra_expect( post_type_exists( 'infra_plato' ), 'Product content type missing.' );
infra_expect( taxonomy_exists( 'infra_categoria' ), 'Menu taxonomy missing.' );
infra_expect( count( inframarinos_menu_groups() ) === 0, 'Activation must not silently publish a fictional menu.' );
$empty = infra_render();
infra_expect( false !== strpos( $empty, 'Estamos preparando la carta' ), 'Empty menu must have a useful message.' );
infra_expect( false === strpos( $empty, 'id="tapa-button"' ), 'Empty selection must not show a broken random button.' );
infra_expect( inframarinos_import_demo() === 10, 'Demo import must create ten products.' );
infra_expect( inframarinos_import_demo() === 0, 'Demo import must be idempotent.' );
$groups = inframarinos_menu_groups();
infra_expect( count( $groups ) === 3, 'Expected three menu categories.' );
infra_expect( $groups[0]['term']->slug === 'tapas', 'Category position must determine order.' );
$dish = $groups[0]['posts'][0];
infra_expect( $dish->post_title === 'La Gilda abisal', 'Product position must determine order.' );
infra_expect( count( inframarinos_theme_tapas() ) === 4, 'Only four tapas should be in the random pool.' );

$editor = get_user_by( 'login', 'infra-manager-test' );
if ( ! $editor ) {
    $editor_id = wp_insert_user( array( 'user_login' => 'infra-manager-test', 'user_pass' => wp_generate_password( 40, true, true ), 'role' => 'encargado_inframarinos' ) );
    infra_expect( ! is_wp_error( $editor_id ), 'Could not create manager account.' );
    $editor = get_user_by( 'id', $editor_id );
}
wp_set_current_user( $editor->ID );
infra_expect( current_user_can( 'manage_inframarinos' ), 'Manager cannot manage bar settings.' );
infra_expect( current_user_can( 'edit_post', $dish->ID ), 'Manager cannot edit a menu product.' );
infra_expect( current_user_can( 'publish_infra_dishes' ) && current_user_can( 'upload_files' ), 'Manager cannot publish products or upload pictures.' );
foreach ( array( 'activate_plugins', 'install_plugins', 'edit_themes', 'manage_options', 'delete_users' ) as $forbidden ) {
    infra_expect( ! current_user_can( $forbidden ), 'Manager has excessive capability: ' . $forbidden );
}
infra_expect( apply_filters( 'option_page_capability_inframarinos', 'manage_options' ) === 'manage_inframarinos', 'Settings permission is incorrect.' );
$_POST = array( 'infra_price' => '999,00', 'infra_available' => '1' );
inframarinos_save_dish( $dish->ID );
infra_expect( get_post_meta( $dish->ID, '_infra_price', true ) === '3.50', 'Save without nonce must be rejected.' );
$_POST = array( 'inframarinos_dish_nonce' => wp_create_nonce( 'inframarinos_dish' ), 'infra_price' => '4,25', 'infra_tapa' => '1' );
inframarinos_save_dish( $dish->ID );
infra_expect( get_post_meta( $dish->ID, '_infra_price', true ) === '4.25', 'Comma decimal failed.' );
infra_expect( get_post_meta( $dish->ID, '_infra_available', true ) === '0', 'Unavailable status failed.' );
infra_expect( count( inframarinos_theme_tapas() ) === 3, 'Unavailable product must not be in the random pool.' );
$_POST['infra_price'] = '<script>99</script>';
inframarinos_save_dish( $dish->ID );
infra_expect( get_post_meta( $dish->ID, '_infra_price', true ) === '4.25', 'Invalid price must preserve existing price.' );
$_POST = array();
foreach ( array( '-2', '1e2', '1,234', array( '4' ) ) as $bad_price ) {
    infra_expect( inframarinos_normalize_price( $bad_price ) === '', 'Invalid price was accepted.' );
}
$draft = wp_insert_post( array( 'post_type' => 'infra_plato', 'post_title' => 'SECRET-DRAFT', 'post_status' => 'draft' ) );
wp_set_object_terms( $draft, array( $groups[0]['term']->term_id ), 'infra_categoria' );
$available_html = infra_render();
infra_expect( false !== strpos( $available_html, 'Agotado por hoy' ), 'Unavailable label missing from frontend.' );
infra_expect( false !== strpos( $available_html, '4,25 €' ), 'Price must use Spanish decimal format.' );
infra_expect( false === strpos( $available_html, 'SECRET-DRAFT' ), 'Draft leaked to public menu.' );

$input = inframarinos_get_settings();
$input['instagram_handle'] = '@carta.nueva';
$input['hero_title'] = "Nuevo titular\nDesde WordPress";
$input['notice_enabled'] = '1';
$input['notice_text'] = 'Este sábado abrimos a las 14:00.';
$input['hours'] = array( array( 'days' => 'Viernes', 'time' => '14:00 — 23:00' ), array( 'days' => '', 'time' => '' ) );
$input['unexpected_key'] = 'should disappear';
$clean = inframarinos_sanitize_settings( $input );
infra_expect( $clean['instagram_handle'] === 'carta.nueva', 'Instagram handle normalization failed.' );
infra_expect( count( $clean['hours'] ) === 1 && $clean['hours'][0]['days'] === 'Viernes', 'Schedule changes failed.' );
infra_expect( ! isset( $clean['unexpected_key'] ), 'Unknown option was accepted.' );
update_option( 'inframarinos_settings', $clean );
$html = infra_render();
infra_expect( false !== strpos( $html, 'https://www.instagram.com/carta.nueva/' ), 'Instagram change did not reach the frontend.' );
infra_expect( false !== strpos( $html, 'Desde WordPress' ) && false !== strpos( $html, 'Este sábado abrimos a las 14:00.' ), 'Headline or announcement change did not reach frontend.' );
$invalid = $clean;
$invalid['instagram_handle'] = 'javascript:alert(1)';
$invalid['map_url'] = 'javascript:alert(1)';
$invalid['hero_intro'] = '<script>alert(1)</script><b>Hola</b>';
$invalid['hero_image'] = array( 'not-an-id' );
$safe = inframarinos_sanitize_settings( $invalid );
infra_expect( $safe['instagram_handle'] === 'carta.nueva', 'Invalid Instagram must preserve previous account.' );
infra_expect( $safe['map_url'] === '' && strpos( $safe['hero_intro'], '<' ) === false, 'Unsafe input was accepted.' );
infra_expect( $safe['hero_image'] === 0, 'Invalid image attachment accepted.' );
ob_start(); inframarinos_heading( "<img src=x onerror=alert(1)>\nFin" ); $escaped = ob_get_clean();
infra_expect( strpos( $escaped, '<img' ) === false, 'Heading output was not escaped.' );
$clean['instagram_handle'] = '';
update_option( 'inframarinos_settings', $clean );
infra_expect( strpos( infra_render(), 'instagram-banner' ) === false, 'Empty Instagram account must hide the banner.' );

// Existing content survives theme changes; the plugin remains its owner.
switch_theme( 'twentytwentyfive' );
infra_expect( get_post( $dish->ID )->post_title === 'La Gilda abisal' && post_type_exists( 'infra_plato' ), 'Changing theme must preserve menu data.' );
switch_theme( 'inframarinos' );
infra_expect( inframarinos_import_demo() === 0 && get_post_meta( $dish->ID, '_infra_price', true ) === '4.25', 'Import must not overwrite edited products.' );
// Restore a representative demo for the final rendered output.
wp_set_current_user( get_user_by( 'login', 'infra-admin-test' )->ID );
update_option( 'inframarinos_settings', inframarinos_defaults() );
update_post_meta( $dish->ID, '_infra_available', '1' );
update_post_meta( $dish->ID, '_infra_price', '3.50' );
wp_delete_post( $draft, true );
file_put_contents( '/tmp/inframarinos-render.html', infra_render() );
ob_start(); inframarinos_settings_page(); $admin = ob_get_clean();
infra_expect( false !== strpos( $admin, 'options.php' ) && false !== strpos( $admin, '_wpnonce' ) && false !== strpos( $admin, 'infra-add-hours' ), 'Management form or nonce missing.' );
file_put_contents( '/tmp/inframarinos-admin.html', $admin );
echo "PASS: $checks integration assertions on real WordPress + MariaDB.\n";
