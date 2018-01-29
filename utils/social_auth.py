
def disallow_new_vk_users(backend, is_new, **kwargs):
    if backend.name.startswith('vk-') and is_new:
        raise Exception('New VK users is not allowed')
