input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    // File upload functionality
    const uploadBtn = document.getElementById('chat-upload');
    const fileInput = document.getElementById('chat-file-input');

    uploadBtn.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', async (e) => {
        const files = Array.from(e.target.files || []);
        if (files.length === 0) return;

        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);

            try {
                const resp = await fetch('/api/file/upload', {
                    method: 'POST',
                    body: formData
                });
                const result = await resp.json();
                if (resp.ok && result.success) {
                    addMessage(`📎 Uploaded: ${file.name}`, 'system');
                } else {
                    addMessage(`❌ Upload failed for ${file.name}: ${result.error || 'Unknown error'}`, 'system');
                }
            } catch (err) {
                addMessage(`❌ Upload error for ${file.name}: ${err.message}`, 'system');
            }
        }

        fileInput.value = '';
    });

    // Typing indicator element (persistent, shown/hidden as needed)
    const typingEl = document.createElement('div');