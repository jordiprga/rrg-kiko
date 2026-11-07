<?php
defined( 'ABSPATH' ) || exit;

function inframarinos_demo_items() {
    return array(
        'tapas' => array( 'name' => 'Para picar', 'order' => 0, 'tapa' => true, 'items' => array(
            array( 'gilda', 'La Gilda abisal', 'Piparra, aceituna y una anchoa que ha visto cosas.', '3.50' ),
            array( 'ensaladilla', 'Ensaladilla de otra vida', 'La de siempre, pero en esta dimensión sale perfecta.', '7.00' ),
            array( 'croquetas', 'Croquetas del multiverso', 'Seis unidades. Crujientes aquí y en todos los universos.', '9.00' ),
            array( 'boquerones', 'Boquerones en la niebla', 'Vinagre del bueno, ajo, perejil y un misterio pequeño.', '8.50' ),
        ) ),
        'bebidas' => array( 'name' => 'Para brindar', 'order' => 1, 'tapa' => false, 'items' => array(
            array( 'cana', 'Caña a contracorriente', 'Bien tirada, bien fría. Con su tapa, que esto es Granada.', '3.00' ),
            array( 'vermu', 'Vermú de las profundidades', 'Rojo, con sifón y una aceituna en órbita.', '4.50' ),
            array( 'vino', 'Vino de una tierra paralela', 'Una copa de la casa. El terruño está en otra frecuencia.', '3.50' ),
            array( 'marea', 'La marea cero', 'Tónica, limón y romero. Todo el viaje, sin alcohol.', '4.00' ),
        ) ),
        'dulce' => array( 'name' => 'El final feliz', 'order' => 2, 'tapa' => false, 'items' => array(
            array( 'torrija', 'La última torrija', 'Pan brioche, canela y ganas de quedarse un rato más.', '5.50' ),
            array( 'pionono', 'Pionono de Saturno', 'Un homenaje a Santa Fe con un anillo de caramelo.', '4.50' ),
        ) ),
    );
}

function inframarinos_import_demo() {
    $created = 0;
    foreach ( inframarinos_demo_items() as $slug => $group ) {
        $term = get_term_by( 'slug', $slug, 'infra_categoria' );
        if ( ! $term ) {
            $new_term = wp_insert_term( $group['name'], 'infra_categoria', array( 'slug' => $slug ) );
            if ( is_wp_error( $new_term ) ) {
                return $new_term;
            }
            $term_id = $new_term['term_id'];
            update_term_meta( $term_id, '_infra_order', $group['order'] );
        } else {
            $term_id = $term->term_id;
        }
        foreach ( $group['items'] as $order => $item ) {
            $existing = get_posts( array( 'post_type' => 'infra_plato', 'post_status' => array( 'publish', 'draft', 'pending', 'private', 'future', 'trash' ), 'meta_key' => '_infra_demo_key', 'meta_value' => $item[0], 'numberposts' => 1, 'fields' => 'ids' ) );
            if ( $existing ) {
                continue;
            }
            $id = wp_insert_post( array( 'post_type' => 'infra_plato', 'post_status' => 'publish', 'post_title' => $item[1], 'post_content' => $item[2], 'menu_order' => $order, 'meta_input' => array( '_infra_demo_key' => $item[0], '_infra_price' => $item[3], '_infra_available' => '1', '_infra_tapa' => $group['tapa'] ? '1' : '0' ) ), true );
            if ( is_wp_error( $id ) ) {
                return $id;
            }
            $assigned = wp_set_object_terms( $id, array( (int) $term_id ), 'infra_categoria' );
            if ( is_wp_error( $assigned ) ) {
                return $assigned;
            }
            ++$created;
        }
    }
    return $created;
}

add_action( 'admin_post_inframarinos_demo', function () {
    if ( ! current_user_can( 'manage_inframarinos' ) ) {
        wp_die( 'No tienes permiso para cargar la carta.', '', array( 'response' => 403 ) );
    }
    check_admin_referer( 'inframarinos_demo' );
    $result = inframarinos_import_demo();
    wp_safe_redirect( add_query_arg( 'inframarinos_demo', is_wp_error( $result ) ? 'error' : 'ok', admin_url( 'admin.php?page=inframarinos-ayuda' ) ) );
    exit;
} );
