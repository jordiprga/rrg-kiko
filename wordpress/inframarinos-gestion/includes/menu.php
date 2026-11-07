<?php
defined( 'ABSPATH' ) || exit;

function inframarinos_register_menu() {
    register_post_type( 'infra_plato', array(
        'labels' => array( 'name' => 'Platos y bebidas', 'singular_name' => 'Producto de la carta', 'add_new_item' => 'Añadir un plato o bebida', 'edit_item' => 'Editar producto', 'not_found' => 'Todavía no hay productos.' ),
        'public' => false, 'show_ui' => true, 'show_in_menu' => 'inframarinos', 'show_in_rest' => true,
        'supports' => array( 'title', 'editor', 'thumbnail', 'page-attributes' ),
        'capability_type' => array( 'infra_dish', 'infra_dishes' ), 'map_meta_cap' => true,
        'menu_icon' => 'dashicons-carrot', 'rewrite' => false,
    ) );
    register_taxonomy( 'infra_categoria', 'infra_plato', array(
        'labels' => array( 'name' => 'Categorías de la carta', 'singular_name' => 'Categoría', 'add_new_item' => 'Añadir categoría' ),
        'public' => false, 'show_ui' => true, 'show_in_rest' => true, 'hierarchical' => true,
        'capabilities' => array( 'manage_terms' => 'manage_inframarinos', 'edit_terms' => 'manage_inframarinos', 'delete_terms' => 'manage_inframarinos', 'assign_terms' => 'edit_infra_dishes' ),
        'rewrite' => false,
    ) );
}
add_action( 'init', 'inframarinos_register_menu' );

add_action( 'admin_menu', function () {
    add_submenu_page( 'inframarinos', 'Categorías de la carta', 'Categorías de la carta', 'manage_inframarinos', 'edit-tags.php?taxonomy=infra_categoria&post_type=infra_plato' );
} );

function inframarinos_normalize_price( $value ) {
    if ( ! is_scalar( $value ) ) {
        return '';
    }
    $value = str_replace( ',', '.', trim( (string) $value ) );
    return preg_match( '/^\d{1,6}(?:\.\d{1,2})?$/D', $value ) ? number_format( (float) $value, 2, '.', '' ) : '';
}

add_action( 'add_meta_boxes_infra_plato', function () {
    add_meta_box( 'inframarinos-details', 'En la carta', 'inframarinos_dish_fields', 'infra_plato', 'side', 'high' );
} );

function inframarinos_dish_fields( $post ) {
    wp_nonce_field( 'inframarinos_dish', 'inframarinos_dish_nonce' );
    $price = get_post_meta( $post->ID, '_infra_price', true );
    ?>
    <p><label for="infra-price"><strong>Precio en euros</strong></label><br><input id="infra-price" name="infra_price" type="text" inputmode="decimal" value="<?php echo esc_attr( str_replace( '.', ',', $price ) ); ?>" placeholder="3,50" class="widefat"></p>
    <p class="description">Usa coma o punto decimal. Sin símbolo €. Déjalo vacío para indicar «Consultar».</p>
    <p><label><input type="checkbox" name="infra_available" value="1" <?php checked( '0' !== get_post_meta( $post->ID, '_infra_available', true ) ); ?>> Disponible</label></p>
    <p><label><input type="checkbox" name="infra_tapa" value="1" <?php checked( '1' === get_post_meta( $post->ID, '_infra_tapa', true ) ); ?>> Puede salir como tapa de la marea</label></p>
    <p>En <strong>Atributos → Orden</strong> elige su posición. Los números más bajos salen primero. Asigna una categoría para que aparezca en la carta.</p>
    <?php
}

function inframarinos_save_dish( $post_id ) {
    if ( wp_is_post_revision( $post_id ) || wp_is_post_autosave( $post_id ) || ! current_user_can( 'edit_post', $post_id ) ) {
        return;
    }
    if ( ! isset( $_POST['inframarinos_dish_nonce'] ) || ! is_string( $_POST['inframarinos_dish_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['inframarinos_dish_nonce'] ) ), 'inframarinos_dish' ) ) {
        return;
    }
    $raw = isset( $_POST['infra_price'] ) ? wp_unslash( $_POST['infra_price'] ) : '';
    $price = inframarinos_normalize_price( $raw );
    if ( '' === $raw || '' !== $price ) {
        update_post_meta( $post_id, '_infra_price', $price );
    } else {
        set_transient( 'inframarinos_price_error_' . get_current_user_id(), true, 60 );
    }
    update_post_meta( $post_id, '_infra_available', isset( $_POST['infra_available'] ) && '1' === $_POST['infra_available'] ? '1' : '0' );
    update_post_meta( $post_id, '_infra_tapa', isset( $_POST['infra_tapa'] ) && '1' === $_POST['infra_tapa'] ? '1' : '0' );
}
add_action( 'save_post_infra_plato', 'inframarinos_save_dish' );

add_action( 'admin_notices', function () {
    $key = 'inframarinos_price_error_' . get_current_user_id();
    if ( get_transient( $key ) ) {
        delete_transient( $key );
        echo '<div class="notice notice-error"><p>El precio no tiene un formato válido. Usa, por ejemplo, 3,50. Se ha conservado el precio anterior.</p></div>';
    }
} );

function inframarinos_category_order_field( $term = null ) {
    $editing = $term instanceof WP_Term;
    $order = $editing ? (int) get_term_meta( $term->term_id, '_infra_order', true ) : 100;
    wp_nonce_field( 'inframarinos_category_order', 'inframarinos_category_nonce' );
    if ( $editing ) {
        echo '<tr class="form-field"><th><label for="infra-order">Posición en la carta</label></th><td>';
    } else {
        echo '<div class="form-field"><label for="infra-order">Posición en la carta</label>';
    }
    echo '<input type="number" min="0" max="9999" id="infra-order" name="infra_order" value="' . esc_attr( $order ) . '"><p class="description">Los números más bajos salen primero.</p>';
    echo $editing ? '</td></tr>' : '</div>';
}
add_action( 'infra_categoria_add_form_fields', 'inframarinos_category_order_field' );
add_action( 'infra_categoria_edit_form_fields', 'inframarinos_category_order_field' );
function inframarinos_save_category_order( $term_id ) {
    if ( current_user_can( 'manage_inframarinos' ) && isset( $_POST['inframarinos_category_nonce'], $_POST['infra_order'] ) && is_string( $_POST['inframarinos_category_nonce'] ) && wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['inframarinos_category_nonce'] ) ), 'inframarinos_category_order' ) && is_scalar( $_POST['infra_order'] ) ) {
        update_term_meta( $term_id, '_infra_order', min( 9999, absint( $_POST['infra_order'] ) ) );
    }
}
add_action( 'created_infra_categoria', 'inframarinos_save_category_order' );
add_action( 'edited_infra_categoria', 'inframarinos_save_category_order' );

function inframarinos_menu_groups() {
    $terms = get_terms( array( 'taxonomy' => 'infra_categoria', 'hide_empty' => true ) );
    if ( is_wp_error( $terms ) ) {
        return array();
    }
    usort( $terms, function ( $a, $b ) {
        $a_order = get_term_meta( $a->term_id, '_infra_order', true );
        $b_order = get_term_meta( $b->term_id, '_infra_order', true );
        $difference = ( '' === $a_order ? 100 : (int) $a_order ) <=> ( '' === $b_order ? 100 : (int) $b_order );
        return $difference ? $difference : strnatcasecmp( $a->name, $b->name );
    } );
    $groups = array();
    foreach ( $terms as $term ) {
        $posts = get_posts( array( 'post_type' => 'infra_plato', 'post_status' => 'publish', 'numberposts' => -1, 'orderby' => array( 'menu_order' => 'ASC', 'title' => 'ASC' ), 'tax_query' => array( array( 'taxonomy' => 'infra_categoria', 'field' => 'term_id', 'terms' => $term->term_id ) ) ) );
        if ( $posts ) {
            $groups[] = array( 'term' => $term, 'posts' => $posts );
        }
    }
    return $groups;
}
