async function sendMessage() {
    const chatInput = document.getElementById('chat-input');
    const message = chatInput.value.trim();
    if (!message && !selectedFile) return;

    setTyping(true);
    chatInput.value = '';

    if (message) {
        addMessage(message, 'user');
        await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message})
        });
    }

    if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        
        // Show upload progress
        const progressMsg = addMessage(`Uploading ${selectedFile.name}...`, 'assistant', false);
        const progressBar = document.createElement('div');
        progressBar.className = 'upload-progress';
        progressBar.style.width = '0%';
        progressMsg.querySelector('.message-content').appendChild(progressBar);

        try {
            const response = await fetch(`/api/file/upload`, {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                const result = await response.json();
                progressBar.style.width = '100%';
                progressBar.style.backgroundColor = '#10b981';
                
                // Follow up with an analysis request
                await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: `I uploaded a file: ${result.path}. Please analyze it.`})
                });
                
                // Update the message to show completion
                setTimeout(() => {
                    progressMsg.querySelector('.message-content').innerHTML = 
                        `✅ File uploaded: ${result.path}<br>Starting analysis...`;
                }, 500);
            } else {
                progressBar.style.backgroundColor = '#ef4444';
                progressMsg.querySelector('.message-content').innerHTML = 
                    `❌ Upload failed: ${response.statusText}`;
            }
        } catch (error) {
            progressMsg.querySelector('.message-content').innerHTML = 
                `❌ Upload error: ${error.message}`;
        } finally {
            selectedFile = null;
            document.getElementById('chat-file-input').value = '';
        }
    }
}