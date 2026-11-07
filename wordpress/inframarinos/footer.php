<?php defined( 'ABSPATH' ) || exit; $settings = inframarinos_theme_settings(); ?>
<footer><a class="footer-brand" href="<?php echo esc_url( home_url( '/' ) ); ?>"><?php echo esc_html( $settings['site_name'] ); ?> ✳</a><p><?php inframarinos_lines( $settings['footer_note'] ); ?></p><button id="developer-joke" aria-expanded="false" aria-controls="developer-note">Hecho con salitre y código <span>↗</span></button><p id="developer-note" hidden>En este universo, PHP significa «Ponme Hielo, Porfa».<br>Y ningún plugin de WordPress rompe la web al actualizarse. Ese sí que es un mundo paralelo.</p></footer>
<?php wp_footer(); ?>
</body></html>
