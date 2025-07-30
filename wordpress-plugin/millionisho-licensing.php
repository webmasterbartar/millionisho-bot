<?php
/**
 * Plugin Name: Millionisho Licensing
 * Plugin URI: https://millionisho.com
 * Description: Generates license keys for Telegram bot access when all products are purchased
 * Version: 1.0.0
 * Author: Millionisho
 * Author URI: https://millionisho.com
 * Text Domain: millionisho-licensing
 */

// Exit if accessed directly
if (!defined('ABSPATH')) {
    exit;
}

// Plugin constants
define('MILLIONISHO_LICENSING_VERSION', '1.0.0');
define('MILLIONISHO_LICENSING_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('MILLIONISHO_LICENSING_PLUGIN_URL', plugin_dir_url(__FILE__));

class Millionisho_Licensing {
    private static $instance = null;
    private $license_key_meta = '_millionisho_license_key';
    
    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }
    
    private function __construct() {
        // Add menu
        add_action('admin_menu', array($this, 'add_admin_menu'));
        
        // Add settings
        add_action('admin_init', array($this, 'register_settings'));
        
        // Add order completed hook
        add_action('woocommerce_order_status_completed', array($this, 'check_order_completion'));
        
        // Add shortcode for license display
        add_shortcode('millionisho_license', array($this, 'license_shortcode'));
        
        // Add user account tab
        add_filter('woocommerce_account_menu_items', array($this, 'add_license_account_menu_item'));
        add_action('woocommerce_account_millionisho-license_endpoint', array($this, 'license_account_content'));
        
        // Register endpoint
        add_action('init', array($this, 'add_endpoints'));
    }
    
    public function add_endpoints() {
        add_rewrite_endpoint('millionisho-license', EP_ROOT | EP_PAGES);
    }
    
    public function add_admin_menu() {
        add_menu_page(
            'Millionisho Licensing',
            'Millionisho',
            'manage_options',
            'millionisho-licensing',
            array($this, 'admin_page'),
            'dashicons-lock',
            30
        );
    }
    
    public function register_settings() {
        register_setting('millionisho_licensing_options', 'millionisho_required_products');
        register_setting('millionisho_licensing_options', 'millionisho_license_prefix');
    }
    
    public function admin_page() {
        ?>
        <div class="wrap">
            <h2>Millionisho Licensing Settings</h2>
            <form method="post" action="options.php">
                <?php
                settings_fields('millionisho_licensing_options');
                do_settings_sections('millionisho_licensing_options');
                ?>
                <table class="form-table">
                    <tr>
                        <th scope="row">Required Product IDs</th>
                        <td>
                            <input type="text" name="millionisho_required_products" 
                                   value="<?php echo esc_attr(get_option('millionisho_required_products')); ?>" 
                                   class="regular-text" />
                            <p class="description">Enter product IDs separated by commas (e.g., "123,456,789")</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">License Key Prefix</th>
                        <td>
                            <input type="text" name="millionisho_license_prefix" 
                                   value="<?php echo esc_attr(get_option('millionisho_license_prefix', 'MILL')); ?>" 
                                   class="regular-text" />
                            <p class="description">Prefix for generated license keys (e.g., "MILL")</p>
                        </td>
                    </tr>
                </table>
                <?php submit_button(); ?>
            </form>
        </div>
        <?php
    }
    
    public function check_order_completion($order_id) {
        $order = wc_get_order($order_id);
        $user_id = $order->get_user_id();
        
        if ($this->has_purchased_all_required_products($user_id)) {
            $this->generate_license_key($user_id);
        }
    }
    
    private function has_purchased_all_required_products($user_id) {
        $required_products = array_map('trim', explode(',', get_option('millionisho_required_products')));
        $purchased_products = $this->get_user_purchased_products($user_id);
        
        return count(array_intersect($required_products, $purchased_products)) === count($required_products);
    }
    
    private function get_user_purchased_products($user_id) {
        $purchased = array();
        
        $orders = wc_get_orders(array(
            'customer_id' => $user_id,
            'status' => 'completed',
            'limit' => -1,
        ));
        
        foreach ($orders as $order) {
            foreach ($order->get_items() as $item) {
                $purchased[] = $item->get_product_id();
            }
        }
        
        return array_unique($purchased);
    }
    
    private function generate_license_key($user_id) {
        // Check if user already has a license
        $existing_key = get_user_meta($user_id, $this->license_key_meta, true);
        if (!empty($existing_key)) {
            return $existing_key;
        }
        
        // Generate new key
        $prefix = get_option('millionisho_license_prefix', 'MILL');
        $random = strtoupper(substr(md5(uniqid(mt_rand(), true)), 0, 16));
        $license_key = $prefix . '-' . $random;
        
        // Save the key
        update_user_meta($user_id, $this->license_key_meta, $license_key);
        
        return $license_key;
    }
    
    public function get_user_license($user_id) {
        return get_user_meta($user_id, $this->license_key_meta, true);
    }
    
    public function license_shortcode($atts) {
        if (!is_user_logged_in()) {
            return '<p>' . __('Please log in to view your license key.', 'millionisho-licensing') . '</p>';
        }
        
        $user_id = get_current_user_id();
        $license_key = $this->get_user_license($user_id);
        
        if (empty($license_key)) {
            if ($this->has_purchased_all_required_products($user_id)) {
                $license_key = $this->generate_license_key($user_id);
            } else {
                return '<p>' . __('Purchase all required products to receive your license key.', 'millionisho-licensing') . '</p>';
            }
        }
        
        return '<div class="millionisho-license">
            <p>' . __('Your License Key:', 'millionisho-licensing') . '</p>
            <code>' . esc_html($license_key) . '</code>
        </div>';
    }
    
    public function add_license_account_menu_item($items) {
        $items['millionisho-license'] = __('License Key', 'millionisho-licensing');
        return $items;
    }
    
    public function license_account_content() {
        echo do_shortcode('[millionisho_license]');
    }
}

// Initialize plugin
function millionisho_licensing_init() {
    return Millionisho_Licensing::get_instance();
}

add_action('plugins_loaded', 'millionisho_licensing_init');

// Activation hook
register_activation_hook(__FILE__, 'millionisho_licensing_activate');

function millionisho_licensing_activate() {
    // Set default options
    add_option('millionisho_license_prefix', 'MILL');
    
    // Flush rewrite rules
    flush_rewrite_rules();
}

// Deactivation hook
register_deactivation_hook(__FILE__, 'millionisho_licensing_deactivate');

function millionisho_licensing_deactivate() {
    flush_rewrite_rules();
} 