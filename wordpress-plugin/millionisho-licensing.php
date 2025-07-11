<?php
/**
 * Plugin Name: Millionisho Licensing
 * Description: سیستم مدیریت لایسنس برای ربات تلگرام میلیونی‌شو
 * Version: 1.0.0
 * Author: Millionisho
 */

// جلوگیری از دسترسی مستقیم به فایل
if (!defined('WPINC')) {
    die;
}

// ثبت API endpoints
add_action('rest_api_init', function () {
    // API بررسی لایسنس
    register_rest_route('licensing/v1', '/verify', array(
        'methods' => 'GET',
        'callback' => 'millionisho_verify_license',
        'permission_callback' => '__return_true'
    ));
});

// تابع بررسی لایسنس
function millionisho_verify_license($request) {
    $key = $request->get_param('key');
    
    if (empty($key)) {
        return array(
            'status' => 'invalid',
            'message' => 'کلید لایسنس وارد نشده است'
        );
    }

    // دریافت لیست لایسنس‌ها
    $licenses = get_option('millionisho_licenses', array());
    
    // بررسی اعتبار لایسنس
    if (isset($licenses[$key])) {
        return array(
            'status' => 'valid',
            'message' => 'لایسنس معتبر است'
        );
    }

    return array(
        'status' => 'invalid',
        'message' => 'لایسنس نامعتبر است'
    );
}

// اضافه کردن منو به پنل مدیریت
add_action('admin_menu', function() {
    add_menu_page(
        'مدیریت لایسنس‌ها',
        'لایسنس میلیونی‌شو',
        'manage_options',
        'millionisho-licenses',
        'millionisho_admin_page',
        'dashicons-lock'
    );
});

// صفحه مدیریت لایسنس‌ها
function millionisho_admin_page() {
    // ذخیره لایسنس جدید
    if (isset($_POST['add_license']) && check_admin_referer('millionisho_add_license')) {
        $key = sanitize_text_field($_POST['license_key']);
        $licenses = get_option('millionisho_licenses', array());
        $licenses[$key] = current_time('mysql');
        update_option('millionisho_licenses', $licenses);
        echo '<div class="notice notice-success"><p>لایسنس با موفقیت اضافه شد.</p></div>';
    }

    // حذف لایسنس
    if (isset($_POST['delete_license']) && check_admin_referer('millionisho_delete_license')) {
        $key = sanitize_text_field($_POST['license_key']);
        $licenses = get_option('millionisho_licenses', array());
        unset($licenses[$key]);
        update_option('millionisho_licenses', $licenses);
        echo '<div class="notice notice-warning"><p>لایسنس با موفقیت حذف شد.</p></div>';
    }

    // نمایش فرم و لیست لایسنس‌ها
    $licenses = get_option('millionisho_licenses', array());
    ?>
    <div class="wrap">
        <h1>مدیریت لایسنس‌های میلیونی‌شو</h1>
        
        <!-- فرم افزودن لایسنس -->
        <div class="card">
            <h2>افزودن لایسنس جدید</h2>
            <form method="post" action="">
                <?php wp_nonce_field('millionisho_add_license'); ?>
                <table class="form-table">
                    <tr>
                        <th><label for="license_key">کلید لایسنس</label></th>
                        <td>
                            <input type="text" id="license_key" name="license_key" class="regular-text" required>
                            <p class="description">کلید لایسنس را وارد کنید</p>
                        </td>
                    </tr>
                </table>
                <p class="submit">
                    <input type="submit" name="add_license" class="button button-primary" value="افزودن لایسنس">
                </p>
            </form>
        </div>

        <!-- جدول لایسنس‌ها -->
        <div class="card">
            <h2>لایسنس‌های موجود</h2>
            <?php if (empty($licenses)): ?>
                <p>هیچ لایسنسی ثبت نشده است.</p>
            <?php else: ?>
                <table class="wp-list-table widefat fixed striped">
                    <thead>
                        <tr>
                            <th>کلید لایسنس</th>
                            <th>تاریخ ثبت</th>
                            <th>عملیات</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($licenses as $key => $date): ?>
                            <tr>
                                <td><?php echo esc_html($key); ?></td>
                                <td><?php echo esc_html($date); ?></td>
                                <td>
                                    <form method="post" action="" style="display:inline;">
                                        <?php wp_nonce_field('millionisho_delete_license'); ?>
                                        <input type="hidden" name="license_key" value="<?php echo esc_attr($key); ?>">
                                        <input type="submit" name="delete_license" class="button button-small button-link-delete" value="حذف" onclick="return confirm('آیا مطمئن هستید؟');">
                                    </form>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            <?php endif; ?>
        </div>
    </div>
    <?php
} 