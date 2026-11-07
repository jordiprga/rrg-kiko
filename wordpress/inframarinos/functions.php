<?php
defined( 'ABSPATH' ) || exit;

add_action( 'after_setup_theme', function () {
    add_theme_support( 'title-tag' );
    add_theme_support( 'post-thumbnails' );
    add_theme_support( 'html5', array( 'search-form', 'comment-form', 'comment-list', 'gallery', 'caption', 'style', 'script' ) );
    add_theme_support( 'responsive-embeds' );
} );

function inframarinos_theme_settings() {
    if ( function_exists( 'inframarinos_get_settings' ) ) {
        return inframarinos_get_settings();
    }
    return array( 'site_name' => get_bloginfo( 'name' ), 'strapline' => get_bloginfo( 'description' ), 'surface_note' => 'Inframarinos', 'surface_meta' => '', 'instagram_handle' => '', 'footer_note' => '' );
}

function inframarinos_heading( $text ) {
    $lines = preg_split( '/\r\n|\r|\n/', trim( $text ) );
    foreach ( $lines as $index => $line ) {
        if ( $index ) {
            echo '<br>';
        }
        echo $index === count( $lines ) - 1 && count( $lines ) > 1 ? '<em>' . esc_html( $line ) . '</em>' : esc_html( $line );
    }
}

function inframarinos_lines( $text ) {
    echo nl2br( esc_html( $text ) );
}

function inframarinos_instagram_url() {
    $settings = inframarinos_theme_settings();
    return empty( $settings['instagram_handle'] ) ? '' : 'https://www.instagram.com/' . rawurlencode( $settings['instagram_handle'] ) . '/';
}

add_filter( 'document_title_parts', function ( $parts ) {
    $settings = inframarinos_theme_settings();
    if ( is_front_page() ) {
        $parts['title'] = $settings['site_name'];
    } elseif ( isset( $parts['site'] ) ) {
        $parts['site'] = $settings['site_name'];
    }
    return $parts;
} );

function inframarinos_theme_tapas() {
    if ( ! post_type_exists( 'infra_plato' ) ) {
        return array();
    }
    $posts = get_posts( array( 'post_type' => 'infra_plato', 'post_status' => 'publish', 'numberposts' => -1, 'meta_query' => array( array( 'key' => '_infra_tapa', 'value' => '1' ), array( 'relation' => 'OR', array( 'key' => '_infra_available', 'value' => '0', 'compare' => '!=' ), array( 'key' => '_infra_available', 'compare' => 'NOT EXISTS' ) ) ) ) );
    return array_map( function ( $post ) {
        return wp_strip_all_tags( $post->post_title ) . ' · ' . wp_strip_all_tags( $post->post_content );
    }, $posts );
}

add_action( 'wp_enqueue_scripts', function () {
    $version = wp_get_theme()->get( 'Version' );
    wp_enqueue_style( 'inframarinos-fonts', get_theme_file_uri( '/assets/fonts.css' ), array(), $version );
    wp_enqueue_style( 'inframarinos-design', get_theme_file_uri( '/assets/site.css' ), array( 'inframarinos-fonts' ), $version );
    wp_enqueue_style( 'inframarinos-wordpress', get_stylesheet_uri(), array( 'inframarinos-design' ), $version );
    wp_enqueue_script( 'inframarinos-site', get_theme_file_uri( '/assets/site.js' ), array(), $version, true );
    wp_add_inline_script( 'inframarinos-site', 'window.inframarinosData = ' . wp_json_encode( array( 'tapas' => inframarinos_theme_tapas() ), JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT ) . ';', 'before' );
} );

add_action( 'wp_head', function () {
    if ( ! is_front_page() ) {
        return;
    }
    $settings = inframarinos_theme_settings();
    $description = isset( $settings['hero_intro'] ) ? $settings['hero_intro'] : get_bloginfo( 'description' );
    $image = ! empty( $settings['hero_image'] ) ? wp_get_attachment_image_url( $settings['hero_image'], 'large' ) : false;
    echo '<meta name="description" content="' . esc_attr( $description ) . '">';
    echo '<meta name="theme-color" content="#173d3b">';
    echo '<meta property="og:title" content="' . esc_attr( $settings['site_name'] ) . '">';
    echo '<meta property="og:description" content="' . esc_attr( $description ) . '">';
    echo '<meta property="og:type" content="website"><meta property="og:url" content="' . esc_url( home_url( '/' ) ) . '">';
    echo '<meta property="og:image" content="' . esc_url( $image ? $image : get_theme_file_uri( '/assets/bar.jpg' ) ) . '">';
}, 5 );

add_action( 'admin_notices', function () {
    if ( ! function_exists( 'inframarinos_get_settings' ) && current_user_can( 'activate_plugins' ) ) {
        echo '<div class="notice notice-warning"><p>Para gestionar la portada y la carta de Inframarinos, instala y activa el plugin incluido <strong>Inframarinos · Gestión del bar</strong>.</p></div>';
    }
} );
