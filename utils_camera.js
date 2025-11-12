/**
 * 摄像头和拍照模块
 * 提供相机控制、图像质量检测和压缩功能
 */

class CameraModule {
    constructor(options = {}) {
        this.videoElement = options.video;
        this.canvasElement = options.canvas;
        this.facingMode = 'environment'; // 后置摄像头
        this.stream = null;
        this.qualityThreshold = 0.7;
    }

    /**
     * 启动摄像头
     */
    async startCamera() {
        try {
            const constraints = {
                video: { 
                    facingMode: this.facingMode,
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                },
                audio: false
            };
            
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            if (this.videoElement) {
                this.videoElement.srcObject = this.stream;
                console.log('✅ 摄像头已启动');
            }
            return true;
        } catch (error) {
            console.error('❌ 无法访问摄像头:', error);
            showNotification('无法访问摄像头，请检查权限', 'error');
            return false;
        }
    }

    /**
     * 切换前后摄像头
     */
    async toggleCamera() {
        this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
        this.stopCamera();
        await this.startCamera();
        showNotification(
            this.facingMode === 'environment' ? '✅ 已切换到后置摄像头' : '✅ 已切换到前置摄像头',
            'info'
        );
    }

    /**
     * 停止摄像头
     */
    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
            if (this.videoElement) {
                this.videoElement.srcObject = null;
            }
            console.log('🛑 摄像头已停止');
        }
    }

    /**
     * 拍照
     */
    capture() {
        if (!this.canvasElement || !this.videoElement) {
            console.error('缺少canvas或video元素');
            return null;
        }

        const canvas = this.canvasElement;
        const ctx = canvas.getContext('2d');
        canvas.width = this.videoElement.videoWidth || 1280;
        canvas.height = this.videoElement.videoHeight || 720;
        
        ctx.drawImage(this.videoElement, 0, 0);
        return canvas.toDataURL('image/jpeg', 0.9);
    }

    /**
     * 检测图像质量
     */
    analyzeQuality(canvas) {
        if (!canvas) return { isGood: false, suggestion: { type: 'error', text: '无法分析' } };

        const ctx = canvas.getContext('2d');
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;

        // 计算亮度
        let brightness = 0;
        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            const avg = (r + g + b) / 3;
            brightness += avg;
        }
        brightness = brightness / (data.length / 4) / 255;

        // 计算对比度和清晰度
        let contrast = 0;
        let edges = 0;
        for (let i = 4; i < data.length - 4; i += 4) {
            const curr = (data[i] + data[i+1] + data[i+2]) / 3;
            const prev = (data[i-4] + data[i-3] + data[i-2]) / 3;
            const diff = Math.abs(curr - prev);
            contrast += diff;
            if (diff > 20) edges++;
        }
        contrast = contrast / (data.length / 4) / 255;
        const clarity = edges / (data.length / 4);

        const quality = {
            brightness: Math.max(0, Math.min(1, brightness)),
            contrast: Math.max(0, Math.min(1, contrast)),
            clarity: Math.max(0, Math.min(1, clarity)),
            overall: (brightness * 0.3 + contrast * 0.3 + clarity * 0.4),
            isGood: brightness > 0.25 && brightness < 0.85 && contrast > 0.1,
            suggestion: this._getQualitySuggestion(brightness, contrast, clarity)
        };

        return quality;
    }

    /**
     * 获取质量建议
     */
    _getQualitySuggestion(brightness, contrast, clarity) {
        if (brightness < 0.25) {
            return { type: 'warning', text: '📸 光线太暗，请到光线充足的地方' };
        }
        if (brightness > 0.85) {
            return { type: 'warning', text: '📸 光线过曝，请避免直射光线' };
        }
        if (contrast < 0.1) {
            return { type: 'warning', text: '📸 对比度不足，请确保主体清晰' };
        }
        if (clarity < 0.15) {
            return { type: 'warning', text: '📸 图像模糊，请稳定手机重新拍摄' };
        }
        return { type: 'success', text: '✅ 图片质量良好，可以分析' };
    }

    /**
     * 压缩图像
     */
    async compressImage(dataUrl, maxWidth = 800, quality = 0.7) {
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const scale = Math.min(1, maxWidth / img.width);
                canvas.width = img.width * scale;
                canvas.height = img.height * scale;
                
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                
                const compressed = canvas.toDataURL('image/jpeg', quality);
                const originalSize = Math.round(dataUrl.length / 1024);
                const compressedSize = Math.round(compressed.length / 1024);
                
                console.log(`📊 图像压缩: ${originalSize}KB → ${compressedSize}KB (${Math.round((1 - compressedSize/originalSize) * 100)}% 节省)`);
                resolve(compressed);
            };
            img.onerror = () => resolve(dataUrl);
            img.src = dataUrl;
        });
    }

    /**
     * 完整流程：拍照->检测->压缩
     */
    async captureAndProcess() {
        // 1. 拍照
        const dataUrl = this.capture();
        if (!dataUrl) return null;

        // 2. 检测质量
        const quality = this.analyzeQuality(this.canvasElement);

        // 3. 如果质量不好给出提示但继续处理
        if (!quality.isGood) {
            showNotification(quality.suggestion.text, quality.suggestion.type, { autoDismiss: false });
        }

        // 4. 压缩
        const compressed = await this.compressImage(dataUrl, 800, 0.7);

        return {
            original: dataUrl,
            compressed: compressed,
            quality: quality
        };
    }
}

// 增强的通知系统（如果还没定义）
if (typeof showNotification === 'undefined') {
    window.showNotification = function(message, type = 'info', options = {}) {
        const config = { 
            autoDismiss: true, 
            timeout: 3000, 
            ...options 
        };
        
        const notification = document.createElement('div');
        const id = `notif-${Date.now()}`;
        notification.id = id;
        
        const colors = {
            'success': '#10b981',
            'error': '#ef4444',
            'warning': '#f59e0b',
            'info': '#3b82f6'
        };
        
        const icons = {
            'success': '✓',
            'error': '✕',
            'warning': '⚠',
            'info': 'ℹ'
        };
        
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 16px 20px;
            background: ${colors[type] || colors.info};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            font-size: 14px;
            max-width: 400px;
            animation: slideIn 0.3s ease-out;
        `;
        
        notification.innerHTML = `
            <div style="display: flex; gap: 12px; align-items: flex-start;">
                <span style="font-size: 18px; flex-shrink: 0;">${icons[type] || icons.info}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 500; margin-bottom: 4px;">${type === 'error' ? '出错了' : type === 'warning' ? '提示' : type === 'success' ? '成功' : '信息'}</div>
                    <div>${message}</div>
                </div>
                ${config.autoDismiss ? '' : '<button onclick="document.getElementById(\''+id+'\').remove()" style="background: none; border: none; color: white; cursor: pointer; font-size: 18px;">×</button>'}
            </div>
        `;
        
        if (!document.querySelector('style[data-notifications]')) {
            const style = document.createElement('style');
            style.setAttribute('data-notifications', 'true');
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(notification);
        
        if (config.autoDismiss) {
            setTimeout(() => notification.remove(), config.timeout);
        }
        
        return id;
    };
}

console.log('✅ CameraModule 已加载');
