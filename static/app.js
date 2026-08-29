(() => {
    const root = document.documentElement;
    const themeToggle = document.getElementById('theme-toggle');
    const preferred = localStorage.getItem('expense-theme');
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = preferred || (systemDark ? 'dark' : 'light');

    themeToggle?.addEventListener('click', () => {
        const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
        root.dataset.theme = next;
        localStorage.setItem('expense-theme', next);
    });

    const dialog = document.getElementById('edit-dialog');
    const editForm = document.getElementById('edit-form');
    const fields = {
        name: document.getElementById('edit-name'),
        amount: document.getElementById('edit-amount'),
        category: document.getElementById('edit-category'),
        date: document.getElementById('edit-date'),
        notes: document.getElementById('edit-notes'),
    };

    document.querySelectorAll('.edit-button').forEach((button) => {
        button.addEventListener('click', () => {
            if (!dialog || !editForm) return;
            editForm.action = `/expenses/${button.dataset.id}/update`;
            fields.name.value = button.dataset.name || '';
            fields.amount.value = button.dataset.amount || '';
            fields.category.value = button.dataset.category || 'Other';
            fields.date.value = button.dataset.date || '';
            fields.notes.value = button.dataset.notes || '';
            dialog.showModal();
            fields.name.focus();
        });
    });

    const closeDialog = () => dialog?.close();
    document.getElementById('dialog-close')?.addEventListener('click', closeDialog);
    document.getElementById('dialog-cancel')?.addEventListener('click', closeDialog);
    dialog?.addEventListener('click', (event) => {
        if (event.target === dialog) closeDialog();
    });

    document.querySelectorAll('[data-delete-form]').forEach((form) => {
        form.addEventListener('submit', (event) => {
            const name = form.dataset.name || 'this expense';
            if (!window.confirm(`Delete ${name}? This cannot be undone.`)) {
                event.preventDefault();
            }
        });
    });

    window.setTimeout(() => {
        document.querySelectorAll('.toast').forEach((toast) => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-6px)';
            window.setTimeout(() => toast.remove(), 180);
        });
    }, 3200);
})();
