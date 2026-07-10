(() => {
    const composer = document.querySelector('[data-composer]');
    if (composer) {
        const message = composer.querySelector('[data-message-input]');
        const media = composer.querySelector('[data-media-input]');
        const preview = composer.querySelector('[data-message-preview]');
        const counter = composer.querySelector('[data-character-count]');
        const limitLabel = composer.querySelector('[data-character-limit]');
        const targetInputs = [...composer.querySelectorAll('[data-target-input]')];
        const channelPreview = composer.querySelector('[data-preview-channels]');

        const updatePreview = () => {
            const text = message.value || 'Текст сообщения появится здесь.';
            preview.textContent = text.replaceAll('[Имя]', 'Анна');
            counter.textContent = message.value.length.toLocaleString('ru-RU');
            const hasMedia = media.files.length > 0;
            const selected = targetInputs.filter((input) => input.checked).map((input) => input.dataset.targetInput);
            const limits = [];
            if (selected.includes('telegram')) limits.push(hasMedia ? 1024 : 4096);
            if (selected.includes('max')) limits.push(4000);
            message.maxLength = limits.length ? Math.min(...limits) : 4096;
            limitLabel.textContent = message.maxLength.toLocaleString('ru-RU');
            counter.parentElement.classList.toggle('limit-warning', message.value.length > message.maxLength);

            channelPreview.replaceChildren();
            selected.forEach((channel) => {
                const badge = document.createElement('span');
                badge.className = `channel-badge ${channel}`;
                badge.textContent = channel === 'telegram' ? 'Telegram' : 'MAX';
                channelPreview.appendChild(badge);
            });
        };

        message.addEventListener('input', updatePreview);
        media.addEventListener('change', updatePreview);
        targetInputs.forEach((input) => input.addEventListener('change', updatePreview));
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
                Object.entries(data.platforms || {}).forEach(([platform, stats]) => {
                    const root = progressRoot.querySelector(`[data-platform="${platform}"]`);
                    if (!root) return;
                    root.querySelector('[data-platform-field="success"]').textContent = stats.success_count;
                    root.querySelector('[data-platform-field="errors"]').textContent = stats.error_count;
                    root.querySelector('[data-platform-field="skipped"]').textContent = stats.skipped_count;
                });
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
