<?php
/** Install an isolated disposable WordPress. Never run on an existing client site. */
define( 'WP_INSTALLING', true );
$_SERVER['HTTP_HOST'] = 'inframarinos-wp';
$_SERVER['SERVER_NAME'] = 'inframarinos-wp';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SERVER_PROTOCOL'] = 'HTTP/1.1';
require '/var/www/html/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/upgrade.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
if ( ! is_blog_installed() ) {
    wp_install( 'Inframarinos QA', 'infra-admin-test', 'qa@example.invalid', false, '', wp_generate_password( 40, true, true ) );
}
update_option( 'home', 'http://inframarinos-wp' );
update_option( 'siteurl', 'http://inframarinos-wp' );
update_option( 'blog_public', '0' );
update_option( 'WPLANG', 'es_ES' );
wp_set_current_user( get_user_by( 'login', 'infra-admin-test' )->ID );
$result = activate_plugin( 'inframarinos-gestion/inframarinos-gestion.php' );
if ( is_wp_error( $result ) ) {
    throw new RuntimeException( $result->get_error_message() );
}
switch_theme( 'inframarinos' );
echo "Installed disposable WordPress and activated theme + management plugin.\n";
