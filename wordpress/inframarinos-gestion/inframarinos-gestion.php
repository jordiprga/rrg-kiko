<?php
/**
 * Plugin Name: Inframarinos · Gestión del bar
 * Description: Carta, categorías, fotografías, avisos y ajustes de Inframarinos. Sin servicios ni plugins de pago.
 * Version: 1.0.0
 * Requires at least: 6.5
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 * Text Domain: inframarinos
 */
defined( 'ABSPATH' ) || exit;
define( 'INFRAMARINOS_PLUGIN_FILE', __FILE__ );

require_once __DIR__ . '/includes/settings.php';
require_once __DIR__ . '/includes/menu.php';
require_once __DIR__ . '/includes/demo.php';

function inframarinos_activate() {
    add_option( 'inframarinos_settings', inframarinos_defaults() );
    $caps = array( 'read', 'upload_files', 'manage_inframarinos', 'edit_infra_dishes', 'edit_others_infra_dishes', 'edit_published_infra_dishes', 'publish_infra_dishes', 'delete_infra_dishes', 'delete_others_infra_dishes', 'delete_published_infra_dishes', 'read_private_infra_dishes', 'edit_private_infra_dishes', 'delete_private_infra_dishes' );
    add_role( 'encargado_inframarinos', 'Encargado de Inframarinos', array( 'read' => true ) );
    foreach ( array( 'administrator', 'encargado_inframarinos' ) as $name ) {
        $role = get_role( $name );
        if ( $role ) {
            foreach ( $caps as $cap ) {
                $role->add_cap( $cap );
            }
        }
    }
    inframarinos_register_menu();
}
register_activation_hook( __FILE__, 'inframarinos_activate' );

add_action( 'admin_menu', function () {
    add_menu_page( 'Inframarinos', 'Inframarinos', 'manage_inframarinos', 'inframarinos', 'inframarinos_settings_page', 'dashicons-store', 25 );
    add_submenu_page( 'inframarinos', 'La web', 'La web', 'manage_inframarinos', 'inframarinos', 'inframarinos_settings_page' );
    add_submenu_page( 'inframarinos', 'Cómo se usa', 'Cómo se usa', 'manage_inframarinos', 'inframarinos-ayuda', 'inframarinos_help_page' );
} );

function inframarinos_help_page() {
    if ( ! current_user_can( 'manage_inframarinos' ) ) {
        return;
    }
    ?>
    <div class="wrap"><h1>Tu barra de mandos</h1>
    <p><a class="button button-primary" href="<?php echo esc_url( home_url( '/' ) ); ?>" target="_blank" rel="noopener">Ver la web ↗</a></p>
    <h2>Cambiar la web</h2><p>En <strong>Inframarinos → La web</strong> puedes cambiar textos, fotografía, Instagram, ubicación, horarios y avisos. Pulsa <strong>Guardar cambios</strong>.</p>
    <h2>Gestionar la carta</h2><p>En <strong>Inframarinos → Platos y bebidas</strong> añade un producto, escribe su descripción, precio y posición, y elige una categoría. Pulsa <strong>Publicar</strong>. La posición más baja sale primero.</p>
    <p>Desmarca <strong>Disponible</strong> para mostrarlo como agotado. Un borrador no aparece en la web. La opción <strong>Puede salir como tapa de la marea</strong> lo añade al sorteo de tapas mientras esté disponible.</p>
    <p>En <strong>Categorías de la carta</strong> puedes crear, renombrar y ordenar categorías. Cada categoría se convierte en una pestaña de la carta. Las categorías sin productos publicados no aparecen.</p>
    <h2>Empezar con el ejemplo</h2><p>Puedes cargar la carta ficticia de Inframarinos y después editarla. Solo se añaden productos de ejemplo que no existan; no se sobrescriben tus cambios. Los precios, horarios y textos iniciales son ficticios: revísalos antes de usarlos para un bar real.</p>
    <form action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" method="post">
    <input type="hidden" name="action" value="inframarinos_demo"><?php wp_nonce_field( 'inframarinos_demo' ); ?>
    <?php submit_button( 'Cargar la carta de ejemplo', 'secondary' ); ?></form>
    <h2>Cuenta del cliente</h2><p>Un administrador puede crear un usuario desde <strong>Usuarios → Añadir nuevo</strong> y asignarle el perfil <strong>Encargado de Inframarinos</strong>. Podrá gestionar estos contenidos y subir fotos, sin instalar plugins ni modificar el tema.</p>
    <p>Si utilizas caché en el alojamiento, vacíala cuando los cambios no aparezcan inmediatamente.</p>
    </div>
    <?php
}

add_action( 'admin_notices', function () {
    if ( current_user_can( 'manage_inframarinos' ) && isset( $_GET['inframarinos_demo'] ) ) {
        $failed = 'error' === sanitize_key( wp_unslash( $_GET['inframarinos_demo'] ) );
        echo '<div class="notice ' . ( $failed ? 'notice-error' : 'notice-success' ) . '"><p>' . esc_html( $failed ? 'No se ha podido completar la importación. Puedes volver a intentarlo sin duplicar los productos ya cargados.' : 'Carta de ejemplo preparada. Los productos existentes conservan tus cambios.' ) . '</p></div>';
    }
} );
