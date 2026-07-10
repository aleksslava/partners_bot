(() => {
    const composer = document.querySelector('[data-composer]');
    if (composer) {
        const message = composer.querySelector('[data-message-input]');
        const media = composer.querySelector('[data-media-input]');
        const preview = composer.querySelector('[data-message-preview]');
        const counter = composer.querySelector('[data-character-count]');

        const updatePreview = () => {
            const text = message.value || 'Текст сообщения появится здесь.';
            preview.textContent = text.replaceAll('[Имя]', 'Анна');
            counter.textContent = message.value.length.toLocaleString('ru-RU');
            const hasMedia = media.files.length > 0;
            message.maxLength = hasMedia ? 1024 : 4096;
            counter.parentElement.classList.toggle('limit-warning', message.value.length > message.maxLength);
        };

        message.addEventListener('input', updatePreview);
        media.addEventListener('change', updatePreview);
        updatePreview();
    }

    document.querySelectorAll('[data-confirm]').forEach((form) => {
        form.addEventListener('submit', (event) => {
            if (!window.confirm(form.dataset.confirm)) event.preventDefault();
        });
    });

    const progressRoot = document.querySelector('[data-broadcast-progress]');
    if (progressRoot && progressRoot.dataset.active === 'true') {
        const poll = async () => {
            try {
                const response = await fetch(progressRoot.dataset.statusUrl, {
                    credentials: 'same-origin',
                    headers: { Accept: 'application/json' },
                });
                if (!response.ok) return;
                const data = await response.json();
                document.querySelector('[data-field="status-label"]').textContent = data.status_label;
                progressRoot.querySelector('[data-field="processed"]').textContent = data.processed_count;
                progressRoot.querySelector('[data-field="success"]').textContent = data.success_count;
                progressRoot.querySelector('[data-field="errors"]').textContent = data.error_count;
                progressRoot.querySelector('[data-field="skipped"]').textContent = data.skipped_count;
                progressRoot.querySelector('[data-field="progress-bar"]').style.width = `${data.progress}%`;
                if (['completed', 'completed_with_errors', 'cancelled'].includes(data.status)) {
                    window.setTimeout(() => window.location.reload(), 500);
                    return;
                }
                window.setTimeout(poll, 1500);
            } catch (_) {
                window.setTimeout(poll, 3000);
            }
        };
        window.setTimeout(poll, 600);
    }
})();
