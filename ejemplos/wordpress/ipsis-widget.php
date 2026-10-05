<?php
/**
 * Plugin Name: ipsis Widget
 * Description: Adds the ipsis Web Component with a shortcode.
 * Version: 0.1.0
 */

if (!defined('ABSPATH')) {
    exit;
}

function ipsis_shortcode($attributes) {
    $attributes = shortcode_atts(
        array(
            'api' => 'http://127.0.0.1:8000',
            'key' => '',
            'title' => 'Help center',
            'color' => '#2563eb',
            'position' => 'bottom-right',
        ),
        $attributes,
        'ipsis'
    );

    $api = untrailingslashit($attributes['api']);
    wp_enqueue_script('ipsis-widget', $api . '/widget.js', array(), null, true);

    return sprintf(
        '<ipsis-chat api="%s" widget-key="%s" title="%s" color="%s" position="%s"></ipsis-chat>',
        esc_url($api),
        esc_attr($attributes['key']),
        esc_attr($attributes['title']),
        esc_attr($attributes['color']),
        esc_attr($attributes['position'])
    );
}
add_shortcode('ipsis', 'ipsis_shortcode');
