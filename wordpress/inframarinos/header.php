<?php defined( 'ABSPATH' ) || exit; $settings = inframarinos_theme_settings(); $instagram = inframarinos_instagram_url(); ?>
<!doctype html>
<html <?php language_attributes(); ?>>
<head><meta charset="<?php bloginfo( 'charset' ); ?>"><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="<?php echo esc_url( get_theme_file_uri( '/assets/fish.svg' ) ); ?>">
<?php wp_head(); ?></head>
<body <?php body_class(); ?>>
<?php wp_body_open(); ?>
<a class="skip-link" href="#contenido">Saltar al contenido</a>
<div class="surface-note"><?php echo esc_html( $settings['surface_note'] ); ?> <span><?php echo esc_html( $settings['surface_meta'] ); ?></span></div>
<header>
  <a class="wordmark" href="<?php echo esc_url( home_url( '/#inicio' ) ); ?>" aria-label="<?php echo esc_attr( $settings['site_name'] . ', inicio' ); ?>"><?php echo esc_html( $settings['site_name'] ); ?><span>.</span></a>
  <p class="masthead-caption"><?php echo esc_html( $settings['strapline'] ); ?></p>
  <nav aria-label="Navegación principal"><a href="<?php echo esc_url( home_url( '/#historia' ) ); ?>">La taberna</a><a href="<?php echo esc_url( home_url( '/#carta' ) ); ?>">La carta</a><a href="<?php echo esc_url( home_url( '/#coordenadas' ) ); ?>">Cómo bajar</a><?php if ( $instagram ) : ?><a href="<?php echo esc_url( $instagram ); ?>" target="_blank" rel="noopener noreferrer" aria-label="<?php echo esc_attr( 'Instagram de @' . $settings['instagram_handle'] . ' (abre en otra pestaña)' ); ?>">Instagram ↗</a><?php endif; ?></nav>
</header>
