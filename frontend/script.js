document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatHistory = document.getElementById('chatHistory');

    // 发送消息的函数
    function sendMessage() {
        const text = messageInput.value.trim();
        
        if (text) {
            // 1. 添加用户消息
            appendMessage(text, 'user');
            
            // 2. 清空输入框
            messageInput.value = '';
            
            // 3. 显示"规划中"状态
            const statusId = 'status-' + Date.now();
            appendThinkingMessage(statusId, '规划中');
            
            // 4. 建立 EventSource 连接接收流式数据
            fetch('http://127.0.0.1:8000/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: text })
            })
            .then(response => {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let todoListId = null;
                
                function processStream() {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            return;
                        }
                        
                        const chunk = decoder.decode(value, { stream: true });
                        const lines = chunk.split('\n');
                        
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                const data = line.substring(6);
                                if (data === '[DONE]') {
                                    return;
                                }
                                
                                try {
                                    const event = JSON.parse(data);
                                    handleEvent(event, statusId);
                                    
                                    if (event.type === 'plan') {
                                        todoListId = createTodoList(event.todos);
                                    } else if (event.type === 'task_complete' && todoListId) {
                                        checkTodoItem(todoListId, event.task_id);
                                    }
                                } catch (e) {
                                    console.error('解析事件失败:', e);
                                }
                            }
                        }
                        
                        processStream();
                    });
                }
                
                processStream();
            })
            .catch(error => {
                console.error('Error:', error);
                const statusMsg = document.getElementById(statusId);
                if (statusMsg) {
                    statusMsg.remove();
                }
                appendMessage('抱歉，服务器连接失败', 'system');
            });
        }
    }

    // 处理服务器推送的事件
    function handleEvent(event, statusId) {
        const statusMsg = document.getElementById(statusId);
        
        switch (event.type) {
            case 'status':
                // 更新状态消息
                if (statusMsg) {
                    updateThinkingMessage(statusMsg, event.content);
                }
                break;
                
            case 'plan':
                // 移除"规划中"状态
                if (statusMsg) {
                    statusMsg.remove();
                }
                break;
                
            case 'final_answer':
                // 显示最终答案
                appendMessage(event.content, 'system');
                break;
                
            case 'error':
                // 显示错误
                if (statusMsg) {
                    statusMsg.remove();
                }
                appendMessage('错误: ' + event.content, 'system');
                break;
        }
    }

    // 创建 TODO 列表
    function createTodoList(todos) {
        const todoId = 'todo-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'system-message');
        messageDiv.id = todoId;

        const bubbleDiv = document.createElement('div');
        bubbleDiv.classList.add('bubble', 'todo-list');
        
        const title = document.createElement('div');
        title.classList.add('todo-title');
        title.textContent = '📋 执行计划';
        bubbleDiv.appendChild(title);
        
        const ul = document.createElement('ul');
        ul.classList.add('todo-items');
        
        todos.forEach(todo => {
            const li = document.createElement('li');
            li.classList.add('todo-item');
            li.setAttribute('data-task-id', todo.id);
            
            const checkbox = document.createElement('span');
            checkbox.classList.add('todo-checkbox');
            checkbox.textContent = '☐';
            
            const text = document.createElement('span');
            text.classList.add('todo-text');
            text.textContent = todo.description;
            
            li.appendChild(checkbox);
            li.appendChild(text);
            ul.appendChild(li);
        });
        
        bubbleDiv.appendChild(ul);
        messageDiv.appendChild(bubbleDiv);
        chatHistory.appendChild(messageDiv);
        scrollToBottom();
        
        return todoId;
    }

    // 标记 TODO 项完成
    function checkTodoItem(todoListId, taskId) {
        const todoList = document.getElementById(todoListId);
        if (!todoList) return;
        
        const todoItem = todoList.querySelector(`[data-task-id="${taskId}"]`);
        if (todoItem) {
            todoItem.classList.add('completed');
            const checkbox = todoItem.querySelector('.todo-checkbox');
            checkbox.textContent = '✓';
        }
    }

    // 添加消息到 DOM
    function appendMessage(text, type, id = null) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        if (id) messageDiv.id = id;
        
        if (type === 'user') {
            messageDiv.classList.add('user-message');
        } else {
            messageDiv.classList.add('system-message');
        }

        const bubbleDiv = document.createElement('div');
        bubbleDiv.classList.add('bubble');
        bubbleDiv.textContent = text;

        messageDiv.appendChild(bubbleDiv);
        chatHistory.appendChild(messageDiv);

        // 滚动到底部
        scrollToBottom();
    }

    // 添加"思考中"消息（带跳动动画）
    function appendThinkingMessage(id, text = '思考中') {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'system-message');
        messageDiv.id = id;

        const bubbleDiv = document.createElement('div');
        bubbleDiv.classList.add('bubble');
        
        const thinkingText = document.createElement('span');
        thinkingText.textContent = text;
        
        const thinkingDots = document.createElement('span');
        thinkingDots.classList.add('thinking');
        thinkingDots.innerHTML = '<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>';
        
        bubbleDiv.appendChild(thinkingText);
        bubbleDiv.appendChild(thinkingDots);
        messageDiv.appendChild(bubbleDiv);
        chatHistory.appendChild(messageDiv);

        scrollToBottom();
    }

    // 更新思考消息的文本
    function updateThinkingMessage(messageElement, newText) {
        const bubble = messageElement.querySelector('.bubble');
        if (bubble) {
            const textSpan = bubble.querySelector('span:first-child');
            if (textSpan) {
                textSpan.textContent = newText;
            }
        }
    }

    // 滚动到底部
    function scrollToBottom() {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // 事件监听
    sendBtn.addEventListener('click', sendMessage);

    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // 初始聚焦
    messageInput.focus();
});
