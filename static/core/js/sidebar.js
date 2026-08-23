// ===== ADMIN SIDEBAR TOGGLE =====
document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const closeBtn = document.getElementById('sidebarClose');

    // Solo si existe el sidebar (usuario superusuario)
    if (!sidebar) return;

    // Botón para abrir (en el header)
    const toggleBtn = document.getElementById('sidebarToggleAdmin');

    function openSidebar() {
        sidebar.classList.add('is-open');
        if (overlay) overlay.classList.add('is-visible');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('is-open');
        if (overlay) overlay.classList.remove('is-visible');
        document.body.style.overflow = '';
    }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', openSidebar);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', closeSidebar);
    }

    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    // Cerrar con Escape
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar.classList.contains('is-open')) {
            closeSidebar();
        }
    });

    // En escritorio, siempre visible
    function handleResize() {
        if (window.innerWidth >= 769) {
            sidebar.classList.add('is-open');
            if (overlay) overlay.classList.remove('is-visible');
            document.body.style.overflow = '';
        } else {
            // En móvil, solo si estaba abierto lo mantenemos
            // Si estaba cerrado, lo dejamos cerrado
            if (!sidebar.classList.contains('is-open')) {
                // No hacer nada
            }
        }
    }

    handleResize();
    window.addEventListener('resize', handleResize);
});