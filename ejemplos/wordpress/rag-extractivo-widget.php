<?php
/**
 * Plugin Name: rag-extractivo Widget
 * Description: Inserta el Web Component de rag-extractivo mediante un shortcode.
 * Version: 0.1.0
 */

if (!defined('ABSPATH')) {
    exit;
}

function rag_extractivo_shortcode($attributes) {
    $attributes = shortcode_atts(
        array(
            'api' => 'http://127.0.0.1:8000',
            'clave' => '',
            'titulo' => 'Ayuda documental',
            'color' => '#2563eb',
            'posicion' => 'abajo-derecha',
        ),
        $attributes,
        'rag_extractivo'
    );

    $api = untrailingslashit($attributes['api']);
    wp_enqueue_script('rag-extractivo-widget', $api . '/widget.js', array(), null, true);

    return sprintf(
        '<rag-extractivo-chat api="%s" widget-key="%s" titulo="%s" color="%s" posicion="%s"></rag-extractivo-chat>',
        esc_url($api),
        esc_attr($attributes['clave']),
        esc_attr($attributes['titulo']),
        esc_attr($attributes['color']),
        esc_attr($attributes['posicion'])
    );
}
add_shortcode('rag_extractivo', 'rag_extractivo_shortcode');
