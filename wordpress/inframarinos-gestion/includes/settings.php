<?php
defined( 'ABSPATH' ) || exit;

function inframarinos_schema() {
    return array(
        'portada' => array( 'title' => 'Portada', 'fields' => array(
            'site_name' => array( 'Nombre de la taberna', 'text', 'inframarinos' ),
            'strapline' => array( 'Debajo del nombre', 'text', 'TABERNA DE MERCADO Y OTROS FONDOS' ),
            'surface_note' => array( 'Frase de la franja superior', 'text', 'GRANADA TIENE DOBLE FONDO.' ),
            'surface_meta' => array( 'Detalle de la franja superior', 'text', 'EDICIÓN DEL MERCADO · SE LEE MEJOR CON UNA CAÑA' ),
            'hero_eyebrow' => array( 'Entradilla', 'text', 'SAN AGUSTÍN, GRANADA · PREGUNTA POR LA ESCALERA DE ABAJO' ),
            'hero_title' => array( 'Titular de portada', 'textarea', "Una caña.\nSu tapa.\nOtro mundo." ),
            'hero_intro' => array( 'Presentación', 'textarea', "El de arriba ya lo arreglamos ayer.\nHoy toca una de boquerones y ver qué pasa." ),
            'hero_image' => array( 'Fotografía de portada', 'image', 0 ),
            'hero_image_alt' => array( 'Descripción de la fotografía', 'text', 'Una taberna cálida y llena de plantas, reinterpretada en tonos submarinos' ),
        ) ),
        'historia' => array( 'title' => 'La taberna', 'fields' => array(
            'story_title' => array( 'Titular', 'textarea', "El mar no llegó a Granada.\nNosotros bajamos a buscarlo." ),
            'story_text_1' => array( 'Primer párrafo', 'textarea', 'En algún lugar, justo debajo del Mercado de San Agustín, hay una barra donde las aceitunas flotan y los relojes marcan la hora del aperitivo.' ),
            'story_text_2' => array( 'Segundo párrafo', 'textarea', 'Se llama Inframarinos. Aquí se viene a lo de toda la vida: pedir una caña, compartir una ración y arreglar el mundo. Aunque sea otro.' ),
            'story_signature' => array( 'Frase final', 'text', 'Mismo barrio. Otra dimensión.' ),
            'footer_note' => array( 'Texto del pie de página', 'textarea', "Una ficción nacida en un bar de Granada.\nSin relación con ningún establecimiento real." ),
        ) ),
        'carta' => array( 'title' => 'Presentación de la carta', 'fields' => array(
            'menu_title' => array( 'Titular de la carta', 'textarea', "Comer, beber.\nY luego ya vemos." ),
            'menu_intro' => array( 'Texto al lado de la carta', 'textarea', "Se pone en el centro.\nSe comparte.\nEl último boquerón se pregunta." ),
            'menu_note' => array( 'Nota sobre precios e impuestos', 'text', 'PRECIOS EN EUROS TERRESTRES · IVA INTERDIMENSIONAL INCLUIDO' ),
            'menu_caption' => array( 'Aclaración de la carta', 'text', 'Carta imaginaria. Antojo bastante real.' ),
        ) ),
        'instagram' => array( 'title' => 'Banner de Instagram', 'fields' => array(
            'instagram_handle' => array( 'Cuenta de Instagram', 'instagram', 'yordiprga' ),
            'instagram_title' => array( 'Titular del banner', 'textarea', "Si subimos a la superficie,\nes por aquí." ),
            'instagram_caption' => array( 'Texto del banner', 'textarea', 'Mientras encontramos el Instagram de este universo, usamos el mío.' ),
            'instagram_label' => array( 'Etiqueta de la cuenta', 'text', 'INSTAGRAM · CUENTA PROVISIONAL' ),
            'instagram_action' => array( 'Texto del enlace', 'text', 'SALIR A TOMAR EL AIRE' ),
        ) ),
        'visita' => array( 'title' => 'Ubicación y horarios', 'fields' => array(
            'visit_title' => array( 'Titular de ubicación', 'textarea', "Donde siempre.\nPero debajo." ),
            'address' => array( 'Dirección', 'textarea', "Mercado de San Agustín\nGranada, Andalucía · Tierra B" ),
            'visit_detail' => array( 'Cómo llegar', 'textarea', "Baja por la escalera que no aparece en los planos.\nSi oyes una conversación y un plato de aceitunas,\nvas bien." ),
            'map_url' => array( 'Enlace del mapa', 'url', 'https://www.google.com/maps/search/?api=1&query=Mercado+de+San+Agust%C3%ADn+Granada' ),
            'hours' => array( 'Horarios', 'hours', array( array( 'days' => 'De martes a domingo', 'time' => '13:00 — hasta que baje la marea' ), array( 'days' => 'Lunes', 'time' => 'Cerrado por cambio de dimensión' ) ) ),
            'reservations' => array( 'Reservas', 'textarea', "No hacemos reservas.\nHacemos hueco en la barra." ),
            'fiction_note' => array( 'Aclaración al pie de los horarios', 'text', 'Todo esto ocurre en una Granada imaginaria.' ),
        ) ),
        'avisos' => array( 'title' => 'Aviso temporal', 'fields' => array(
            'notice_enabled' => array( 'Mostrar el aviso', 'checkbox', false ),
            'notice_text' => array( 'Texto del aviso', 'textarea', '' ),
        ) ),
    );
}

function inframarinos_defaults() {
    $result = array();
    foreach ( inframarinos_schema() as $section ) {
        foreach ( $section['fields'] as $key => $field ) {
            $result[ $key ] = $field[2];
        }
    }
    return $result;
}

function inframarinos_get_settings() {
    $saved = get_option( 'inframarinos_settings', array() );
    return array_merge( inframarinos_defaults(), is_array( $saved ) ? $saved : array() );
}

function inframarinos_sanitize_settings( $input ) {
    $input = is_array( $input ) ? $input : array();
    $previous = inframarinos_get_settings();
    $result = array();
    foreach ( inframarinos_schema() as $section ) {
        foreach ( $section['fields'] as $key => $field ) {
            $type = $field[1];
            $raw = isset( $input[ $key ] ) ? $input[ $key ] : ( 'checkbox' === $type ? false : ( 'hours' === $type ? array() : $field[2] ) );
            if ( 'hours' === $type ) {
                $result[ $key ] = array();
                foreach ( array_slice( is_array( $raw ) ? $raw : array(), 0, 20 ) as $row ) {
                    if ( ! is_array( $row ) ) {
                        continue;
                    }
                    $days = isset( $row['days'] ) && is_scalar( $row['days'] ) ? sanitize_text_field( $row['days'] ) : '';
                    $time = isset( $row['time'] ) && is_scalar( $row['time'] ) ? sanitize_text_field( $row['time'] ) : '';
                    if ( '' !== $days || '' !== $time ) {
                        $result[ $key ][] = array( 'days' => $days, 'time' => $time );
                    }
                }
            } elseif ( 'image' === $type ) {
                $id = is_scalar( $raw ) ? absint( $raw ) : 0;
                $result[ $key ] = $id && wp_attachment_is_image( $id ) ? $id : 0;
            } elseif ( 'checkbox' === $type ) {
                $result[ $key ] = is_scalar( $raw ) && in_array( (string) $raw, array( '1', 'true' ), true );
            } elseif ( 'instagram' === $type ) {
                $handle = is_scalar( $raw ) ? ltrim( trim( (string) $raw ), '@' ) : '';
                if ( '' !== $handle && ! preg_match( '/^[a-zA-Z0-9._]{1,30}$/D', $handle ) ) {
                    if ( function_exists( 'add_settings_error' ) ) {
                        add_settings_error( 'inframarinos_settings', 'instagram_invalid', 'Instagram: escribe solo el nombre de usuario, por ejemplo @yordiprga. Se ha conservado la cuenta anterior.' );
                    }
                    $handle = $previous[ $key ];
                }
                $result[ $key ] = $handle;
            } elseif ( 'url' === $type ) {
                $result[ $key ] = is_scalar( $raw ) ? esc_url_raw( $raw, array( 'http', 'https' ) ) : '';
            } else {
                $value = is_scalar( $raw ) ? (string) $raw : '';
                $result[ $key ] = 'textarea' === $type ? sanitize_textarea_field( $value ) : sanitize_text_field( $value );
            }
        }
    }
    return $result;
}

add_action( 'admin_init', function () {
    register_setting( 'inframarinos', 'inframarinos_settings', array( 'type' => 'array', 'sanitize_callback' => 'inframarinos_sanitize_settings', 'default' => inframarinos_defaults(), 'show_in_rest' => false ) );
} );
add_filter( 'option_page_capability_inframarinos', function () { return 'manage_inframarinos'; } );

function inframarinos_settings_page() {
    if ( ! current_user_can( 'manage_inframarinos' ) ) {
        return;
    }
    $settings = inframarinos_get_settings();
    ?>
    <div class="wrap inframarinos-admin"><h1>La web de tu bar</h1>
    <p>Cambia el contenido; el diseño se queda en su sitio. Los cambios se publican al guardar.</p>
    <p><a class="button" href="<?php echo esc_url( home_url( '/' ) ); ?>" target="_blank" rel="noopener">Ver la web ↗</a> <a class="button" href="<?php echo esc_url( admin_url( 'edit.php?post_type=infra_plato' ) ); ?>">Gestionar la carta</a> <a class="button" href="<?php echo esc_url( admin_url( 'admin.php?page=inframarinos-ayuda' ) ); ?>">Cómo se usa</a></p>
    <?php settings_errors( 'inframarinos_settings' ); ?>
    <nav class="infra-section-links" aria-label="Secciones de ajustes"><?php foreach ( inframarinos_schema() as $slug => $section ) : ?><a href="#infra-<?php echo esc_attr( $slug ); ?>"><?php echo esc_html( $section['title'] ); ?></a><?php endforeach; ?></nav>
    <form action="options.php" method="post"><?php settings_fields( 'inframarinos' ); ?>
    <?php foreach ( inframarinos_schema() as $slug => $section ) : ?>
    <section class="infra-settings-section" id="infra-<?php echo esc_attr( $slug ); ?>"><h2><?php echo esc_html( $section['title'] ); ?></h2>
    <table class="form-table" role="presentation"><tbody>
    <?php foreach ( $section['fields'] as $key => $field ) : ?>
    <tr><th scope="row"><label for="infra-<?php echo esc_attr( $key ); ?>"><?php echo esc_html( $field[0] ); ?></label></th><td>
    <?php inframarinos_render_field( $key, $field, $settings[ $key ] ); ?>
    </td></tr>
    <?php endforeach; ?></tbody></table></section>
    <?php endforeach; submit_button( 'Guardar cambios de la web' ); ?>
    </form></div>
    <?php
}

function inframarinos_render_field( $key, $field, $value ) {
    $name = 'inframarinos_settings[' . $key . ']';
    $id = 'infra-' . $key;
    if ( 'textarea' === $field[1] ) {
        echo '<textarea class="large-text" rows="3" id="' . esc_attr( $id ) . '" name="' . esc_attr( $name ) . '">' . esc_textarea( $value ) . '</textarea>';
        if ( in_array( $key, array( 'hero_title', 'story_title', 'menu_title', 'instagram_title', 'visit_title' ), true ) ) {
            echo '<p class="description">Una línea por renglón. La última línea lleva el acento de color. Los titulares cortos encajan mejor.</p>';
        }
    } elseif ( 'checkbox' === $field[1] ) {
        echo '<input type="checkbox" id="' . esc_attr( $id ) . '" name="' . esc_attr( $name ) . '" value="1" ' . checked( $value, true, false ) . '> <span>Activar</span>';
    } elseif ( 'image' === $field[1] ) {
        echo '<div class="infra-image-control"><input type="hidden" id="' . esc_attr( $id ) . '" name="' . esc_attr( $name ) . '" value="' . esc_attr( $value ) . '"><div class="infra-image-preview">';
        if ( $value ) {
            echo wp_get_attachment_image( $value, 'medium' );
        }
        echo '</div><button type="button" class="button infra-select-image">Elegir o subir fotografía</button> <button type="button" class="button infra-clear-image">Usar foto original</button></div>';
        echo '<p class="description">Se recomienda una fotografía horizontal. La foto original se usa si no eliges otra.</p>';
    } elseif ( 'hours' === $field[1] ) {
        echo '<div id="' . esc_attr( $id ) . '" class="infra-hours">';
        foreach ( $value as $index => $row ) {
            inframarinos_hours_row( $index, $row );
        }
        echo '</div><button type="button" id="infra-add-hours" class="button">Añadir franja horaria</button><template id="infra-hours-template">';
        inframarinos_hours_row( '__INDEX__', array( 'days' => '', 'time' => '' ) );
        echo '</template>';
    } else {
        $type = 'url' === $field[1] ? 'url' : 'text';
        echo '<input class="regular-text" type="' . esc_attr( $type ) . '" id="' . esc_attr( $id ) . '" name="' . esc_attr( $name ) . '" value="' . esc_attr( $value ) . '">';
        if ( 'instagram' === $field[1] ) {
            echo '<p class="description">Solo el usuario, con o sin @. Deja el campo vacío para ocultar el banner y el enlace de Instagram.</p>';
        }
    }
}

function inframarinos_hours_row( $index, $row ) {
    $prefix = 'inframarinos_settings[hours][' . $index . ']';
    echo '<div class="infra-hours-row"><label>Días<input type="text" name="' . esc_attr( $prefix . '[days]' ) . '" value="' . esc_attr( $row['days'] ) . '" placeholder="De martes a domingo"></label><label>Horario<input type="text" name="' . esc_attr( $prefix . '[time]' ) . '" value="' . esc_attr( $row['time'] ) . '" placeholder="13:00 — 23:00"></label><button class="button infra-remove-hours" type="button" aria-label="Eliminar esta franja horaria">Eliminar</button></div>';
}

add_action( 'admin_enqueue_scripts', function ( $hook ) {
    if ( 'toplevel_page_inframarinos' !== $hook ) {
        return;
    }
    wp_enqueue_media();
    wp_enqueue_script( 'inframarinos-admin', plugins_url( 'admin.js', INFRAMARINOS_PLUGIN_FILE ), array( 'media-views' ), '1.0.0', true );
    wp_enqueue_style( 'inframarinos-admin', plugins_url( 'admin.css', INFRAMARINOS_PLUGIN_FILE ), array(), '1.0.0' );
} );
