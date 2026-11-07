<?php
$_SERVER['HTTP_HOST'] = 'inframarinos-wp';
$_SERVER['SERVER_NAME'] = 'inframarinos-wp';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SERVER_PROTOCOL'] = 'HTTP/1.1';
require '/var/www/html/wp-load.php';
if ( 'http://inframarinos-wp' !== home_url() ) {
    throw new RuntimeException( 'Refusing to run outside isolated QA.' );
}
if ( function_exists( 'inframarinos_get_settings' ) ) {
    throw new RuntimeException( 'Plugin must be deactivated before this test.' );
}
ob_start();
include get_theme_file_path( '/front-page.php' );
$html = ob_get_clean();
if ( false === strpos( $html, 'La barra está casi lista.' ) ) {
    throw new RuntimeException( 'Missing-plugin fallback failed.' );
}
echo "PASS: theme renders safely without management plugin.\n";
