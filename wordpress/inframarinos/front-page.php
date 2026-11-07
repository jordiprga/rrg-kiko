<?php
defined( 'ABSPATH' ) || exit;
get_header();
if ( ! function_exists( 'inframarinos_get_settings' ) ) : ?>
<main id="contenido" class="wordpress-content"><h1>La barra está casi lista.</h1><p>Estamos preparando la carta y los detalles de la taberna.</p></main>
<?php get_footer(); return; endif;
$settings = inframarinos_get_settings();
?>
  <main id="contenido">
    <?php if ( ! empty( $settings['notice_enabled'] ) && '' !== $settings['notice_text'] ) : ?>
    <aside class="bar-notice" aria-label="Aviso de la taberna"><?php inframarinos_lines( $settings['notice_text'] ); ?></aside>
    <?php endif; ?>
    <section class="hero" id="inicio">
      <div class="hero-copy">
        <p class="eyebrow"><?php echo esc_html( $settings['hero_eyebrow'] ); ?></p>
        <h1><?php inframarinos_heading( $settings['hero_title'] ); ?></h1>
        <p class="intro"><?php inframarinos_lines( $settings['hero_intro'] ); ?></p>
        <a class="button" href="#carta">Bajar a la carta <span>↓</span></a>
        <div class="hero-foot"><span>NO SE FÍA.<br>SALVO A LOS PECES.</span><span>LA TAPA, CON LA BEBIDA.<br>LA CHARLA, POR CUENTA DE LA CASA.</span></div>
      </div>
      <div class="hero-art">
        <?php
        $image_url = $settings['hero_image'] ? wp_get_attachment_image_url( $settings['hero_image'], 'large' ) : false;
        ?>
        <img class="bar-photo" src="<?php echo esc_url( $image_url ? $image_url : get_theme_file_uri( '/assets/bar.jpg' ) ); ?>" alt="<?php echo esc_attr( $settings['hero_image_alt'] ); ?>" fetchpriority="high" width="1400" height="933">
        <div class="photo-wash"></div>
        <div class="depth-label">FOTO ENCONTRADA AL OTRO LADO DEL MERCADO</div>
        <div class="stamp">SE ESTÁ<br><i>en la gloria.</i><span>AUNQUE SEA BAJO EL AGUA</span></div>
        <img class="hero-fish" src="<?php echo esc_url( get_theme_file_uri( '/assets/fish.svg' ) ); ?>" alt="" width="510" height="260">
        <div class="bar-ticket"><span><?php echo esc_html( strtoupper( $settings['site_name'] ) ); ?></span><span>MESA 00 · UNIVERSO B</span><div><span>2 cañas</span><span>✓</span></div><div><span>2 tapas</span><span>✓</span></div><div><span>1 tarde entera</span><span>✓</span></div><strong>TOTAL: QUÉ A GUSTO.</strong><span>GUÁRDELO POR SI VUELVE A LA REALIDAD</span></div>
        <div class="photo-caption"><span>EL LOCAL ES IMAGINARIO.</span><span>LAS GANAS DE QUEDARSE, NO.</span></div>
      </div>
    </section>
    <?php if ( inframarinos_instagram_url() ) : ?>
    <a class="instagram-banner" href="<?php echo esc_url( inframarinos_instagram_url() ); ?>" target="_blank" rel="noopener noreferrer" aria-label="<?php echo esc_attr( 'Visitar Instagram de @' . $settings['instagram_handle'] . ' (abre en otra pestaña)' ); ?>">
      <span class="instagram-postmark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><rect x="4" y="4" width="24" height="24" rx="7"/><circle cx="16" cy="16" r="6"/><circle cx="23" cy="9" r="1" fill="currentColor" stroke="none"/></svg>ENVÍOS A LA<br>SUPERFICIE</span>
      <span class="instagram-message"><span class="instagram-kicker">AVISO A LA PARROQUIA</span><strong><?php inframarinos_heading( $settings['instagram_title'] ); ?></strong><span class="instagram-caption"><?php inframarinos_lines( $settings['instagram_caption'] ); ?></span></span>
      <span class="instagram-account"><span><?php echo esc_html( $settings['instagram_label'] ); ?></span><strong>@<?php echo esc_html( $settings['instagram_handle'] ); ?></strong><span class="instagram-action"><?php echo esc_html( $settings['instagram_action'] ); ?> <span aria-hidden="true">↗</span></span></span>
    </a>
    <?php endif; ?>
    <section class="story section-space" id="historia">
      <div class="section-kicker">LO QUE SE CUENTA EN LA BARRA</div>
      <div class="story-main"><h2><?php inframarinos_heading( $settings['story_title'] ); ?></h2><div class="story-columns"><p><?php inframarinos_lines( $settings['story_text_1'] ); ?></p><p><?php inframarinos_lines( $settings['story_text_2'] ); ?></p></div><p class="handwritten"><?php echo esc_html( $settings['story_signature'] ); ?> <span>↝</span></p></div>
    </section>
    <section class="menu-section section-space" id="carta">
      <div class="menu-heading"><div><p class="section-kicker">HOY HA LLEGADO ESTO DEL MERCADO</p><h2><?php inframarinos_heading( $settings['menu_title'] ); ?></h2></div><p><?php inframarinos_lines( $settings['menu_intro'] ); ?></p></div>
      <?php $groups = inframarinos_menu_groups(); ?>
      <?php if ( $groups ) : ?>
      <div class="menu-tabs" role="tablist" aria-label="Secciones de la carta">
        <?php foreach ( $groups as $index => $group ) : $term_id = $group['term']->term_id; ?>
        <button id="tab-<?php echo esc_attr( $term_id ); ?>" role="tab" aria-selected="<?php echo $index ? 'false' : 'true'; ?>" aria-controls="panel-<?php echo esc_attr( $term_id ); ?>" tabindex="<?php echo $index ? '-1' : '0'; ?>"><?php echo esc_html( $group['term']->name ); ?> <span><?php echo esc_html( str_pad( count( $group['posts'] ), 2, '0', STR_PAD_LEFT ) ); ?></span></button>
        <?php endforeach; ?>
      </div>
      <?php foreach ( $groups as $index => $group ) : $term_id = $group['term']->term_id; ?>
      <div id="panel-<?php echo esc_attr( $term_id ); ?>" class="menu-grid" role="tabpanel" aria-labelledby="tab-<?php echo esc_attr( $term_id ); ?>" tabindex="0" <?php echo $index ? 'hidden' : ''; ?>>
        <?php foreach ( $group['posts'] as $dish ) :
            $available = '0' !== get_post_meta( $dish->ID, '_infra_available', true );
            $price = get_post_meta( $dish->ID, '_infra_price', true ); ?>
        <article class="dish<?php echo $available ? '' : ' dish-unavailable'; ?>">
          <?php if ( has_post_thumbnail( $dish->ID ) ) { echo get_the_post_thumbnail( $dish->ID, 'thumbnail', array( 'class' => 'dish-photo', 'loading' => 'lazy' ) ); } ?>
          <div class="dish-copy"><h3><?php echo esc_html( $dish->post_title ); ?></h3><p><?php echo esc_html( wp_strip_all_tags( $dish->post_content ) ); ?></p><?php if ( ! $available ) : ?><span class="dish-status">Agotado por hoy</span><?php endif; ?></div>
          <span class="price"><?php echo esc_html( '' === $price ? 'Consultar' : number_format( (float) $price, 2, ',', '.' ) . ' €' ); ?></span>
        </article>
        <?php endforeach; ?>
      </div>
      <?php endforeach; ?>
      <?php else : ?>
      <p class="menu-empty">Estamos preparando la carta. Enseguida te contamos qué hay hoy.</p>
      <?php endif; ?>
      <div class="menu-bottom"><span><?php echo esc_html( $settings['menu_note'] ); ?></span><span><?php echo esc_html( $settings['menu_caption'] ); ?></span></div>
    </section>
    <section class="ritual section-space"><div class="ritual-fish"><img src="<?php echo esc_url( get_theme_file_uri( '/assets/fish.svg' ) ); ?>" width="510" height="260" alt="Ilustración de una sardina"><span>EL RITUAL DE LA CASA</span></div><div><p class="eyebrow">PIDE ALGO. PASA ALGO.</p><h2>Tu primera tapa<br>la elige <em>la marea.</em></h2><p>En Granada la tapa acompaña a la bebida.<br>Aquí, además, viene de un universo distinto.</p><?php if ( inframarinos_theme_tapas() ) : ?><button class="button light" id="tapa-button">A ver qué me toca <span>↗</span></button><p id="tapa-result" class="tapa-result" aria-live="polite">La barra está lista. Tú dirás.</p><?php else : ?><p class="tapa-result">Hoy la marea descansa. Pregunta en la barra.</p><?php endif; ?></div></section>
    <section class="visit section-space" id="coordenadas"><div><p class="section-kicker">POR SI PREGUNTAS DÓNDE ES</p><h2><?php inframarinos_heading( $settings['visit_title'] ); ?></h2><p><?php inframarinos_lines( $settings['address'] ); ?></p><p class="visit-detail"><?php inframarinos_lines( $settings['visit_detail'] ); ?></p><a href="<?php echo esc_url( $settings['map_url'] ); ?>" target="_blank" rel="noopener noreferrer" class="map-link">Encontrar el mercado del universo real <span>↗</span></a></div><div class="hours"><span class="small-star">✳</span><p class="eyebrow">HORARIO DE ESTE UNIVERSO</p><?php foreach ( $settings['hours'] as $hours ) : ?><div><span><?php echo esc_html( $hours['days'] ); ?></span><span><?php echo esc_html( $hours['time'] ); ?></span></div><?php endforeach; ?><p><?php inframarinos_lines( $settings['reservations'] ); ?></p><span class="fiction-note"><?php echo esc_html( $settings['fiction_note'] ); ?></span></div></section>
    <section class="closing"><p>DEJA EL MUNDO ARRIBA.</p><a href="#inicio">Aquí abajo<br><em>se está bien.</em> <span>↗</span></a></section>
  </main>
<?php get_footer(); ?>
