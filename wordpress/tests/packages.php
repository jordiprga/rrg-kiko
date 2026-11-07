<?php
/** Verify native WordPress ZIP installation on a fresh disposable site. */
define( 'WP_INSTALLING', true );
define( 'FS_METHOD', 'direct' );
$_SERVER['HTTP_HOST'] = 'inframarinos-package-wp';
$_SERVER['SERVER_NAME'] = 'inframarinos-package-wp';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SERVER_PROTOCOL'] = 'HTTP/1.1';
require '/var/www/html/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/upgrade.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
require_once ABSPATH . 'wp-admin/includes/file.php';
require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
if ( $table_prefix !== 'zipqa_' ) {
    throw new RuntimeException( 'Refusing to run outside the package test database.' );
}
if ( ! is_blog_installed() ) {
    wp_install( 'Inframarinos package QA', 'package-admin', 'qa@example.invalid', false, '', wp_generate_password( 40, true, true ) );
}
wp_set_current_user( get_user_by( 'login', 'package-admin' )->ID );
WP_Filesystem();
$skin = new Automatic_Upgrader_Skin();
$theme = new Theme_Upgrader( $skin );
$result = $theme->install( '/packages/inframarinos-tema.zip' );
if ( is_wp_error( $result ) || ! $result ) {
    throw new RuntimeException( 'Native theme ZIP installation failed.' );
}
$plugin = new Plugin_Upgrader( new Automatic_Upgrader_Skin() );
$result = $plugin->install( '/packages/inframarinos-gestion.zip' );
if ( is_wp_error( $result ) || ! $result ) {
    throw new RuntimeException( 'Native plugin ZIP installation failed.' );
}
$result = activate_plugin( 'inframarinos-gestion/inframarinos-gestion.php' );
if ( is_wp_error( $result ) ) {
    throw new RuntimeException( $result->get_error_message() );
}
switch_theme( 'inframarinos' );
if ( wp_get_theme()->errors() || wp_get_theme()->get( 'Name' ) !== 'Inframarinos' || ! is_plugin_active( 'inframarinos-gestion/inframarinos-gestion.php' ) ) {
    throw new RuntimeException( 'Installed packages are not active and valid.' );
}
echo "PASS: native WordPress theme and plugin ZIP installation and activation.\n";
