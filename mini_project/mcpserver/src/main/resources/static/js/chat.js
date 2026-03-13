const { createApp } = Vue;

createApp({
    data() {
        return {
            messages: [],
            inputMessage: '',
            isTyping: false,
            isConnected: false,
            error: null,
            conversationId: ''
        };
    },

    async mounted() {
        this.conversationId = this.loadConversationId();
        await this.initializeChat();
    },

    methods: {
        async initializeChat() {
            await this.checkHealth();
            await this.fetchMessages();

            if (this.messages.length === 0) {
                this.addMessage('Spring AI 질문을 입력해 주세요. 기본 Q&A 모드로 동작 중입니다.', 'bot');
            }
        },

        async checkHealth() {
            try {
                const response = await fetch('/api/chat/health');
                this.isConnected = response.ok;
                this.error = response.ok ? null : '채팅 API 상태를 확인할 수 없습니다.';
            } catch (error) {
                this.isConnected = false;
                this.error = '채팅 API 연결에 실패했습니다.';
                console.error('헬스 체크 오류:', error);
            }
        },

        async fetchMessages() {
            try {
                const response = await fetch(`/api/chat/messages?conversationId=${encodeURIComponent(this.conversationId)}`);
                if (!response.ok) {
                    throw new Error('대화 이력을 불러오지 못했습니다.');
                }

                const items = await response.json();
                this.messages = items.map((item) => ({
                    id: item.id,
                    content: item.content,
                    structuredAnswer: item.structuredAnswer,
                    type: item.role === 'USER' ? 'user' : 'bot',
                    timestamp: item.createdAt
                }));

                this.$nextTick(() => {
                    this.scrollToBottom();
                });
            } catch (error) {
                this.error = error.message;
                console.error('이력 조회 오류:', error);
            }
        },

        async sendMessage() {
            if (!this.inputMessage.trim() || !this.isConnected || this.isTyping) {
                return;
            }

            const message = this.inputMessage.trim();
            this.addMessage(message, 'user');
            this.inputMessage = '';
            this.isTyping = true;
            this.error = null;

            try {
                const response = await fetch('/api/chat/messages', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        question: message,
                        conversationId: this.conversationId
                    })
                });

                if (!response.ok) {
                    const errorBody = await response.json().catch(() => null);
                    throw new Error(errorBody?.message || '질문 전송에 실패했습니다.');
                }

                const result = await response.json();
                this.addMessage(result.answer, 'bot', result.structuredAnswer);
            } catch (error) {
                this.isTyping = false;
                this.error = error.message;
                console.error('메시지 전송 오류:', error);
                return;
            }

            this.isTyping = false;
        },

        addMessage(content, type, structuredAnswer = null) {
            const message = {
                id: Date.now() + Math.random(),
                content,
                structuredAnswer,
                type,
                timestamp: new Date().toISOString()
            };

            this.messages.push(message);
            this.$nextTick(() => {
                this.scrollToBottom();
            });
        },

        scrollToBottom() {
            const container = this.$refs.messagesContainer;
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        },

        hasItems(items) {
            return Array.isArray(items) && items.length > 0;
        },

        formatSourceName(source) {
            if (!source) {
                return 'unknown';
            }

            const parts = source.split('/');
            return parts[parts.length - 1];
        },

        loadConversationId() {
            const storageKey = 'mcp-chat-conversation-id';
            const existing = window.localStorage.getItem(storageKey);
            if (existing) {
                return existing;
            }

            const generated = `conv-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
            window.localStorage.setItem(storageKey, generated);
            return generated;
        }
    }
}).mount('#app');
