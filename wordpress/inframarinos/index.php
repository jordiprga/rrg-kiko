<?php
defined( 'ABSPATH' ) || exit;
get_header();
?>
<main id="contenido" class="wordpress-content">
<?php if ( have_posts() ) : while ( have_posts() ) : the_post(); ?>
<article <?php post_class(); ?>><h1><?php the_title(); ?></h1><?php the_content(); ?></article>
<?php endwhile; the_posts_pagination(); else : ?>
<h1>No encontramos esta página.</h1><p><a href="<?php echo esc_url( home_url( '/' ) ); ?>">Volver a la taberna</a></p>
<?php endif; ?>
</main>
<?php get_footer(); ?>
