// 个性化用药管理前端脚本

const API_BASE = 'http://localhost:5000/api';
let currentUser = null;
let sessionId = null;
let medications = [];
let reminders = [];
let intakeRecords = [];
let userRecords = [];  // 用户的健康档案列表
let currentRecordFilter = null;  // 当前档案筛选

// 快速返回首页函数（超优化版本）
function goBack() {
    // 清理所有定时器，防止内存泄漏
    clearAllTimers();
    
    // 清理数据，减少内存占用
    medications = [];
    reminders = [];
    intakeRecords = [];
    userRecords = [];
    
    // 移除所有事件监听器
    document.removeEventListener('DOMContentLoaded', null);
    
    // 使用最快的方法返回
    if (document.referrer && document.referrer.includes('index.html')) {
        // 如果是从首页来的，使用history返回（最快，无需加载）
        window.history.back();
    } else {
        // 否则直接跳转到首页（replace不增加历史记录）
        window.location.replace('index.html');
    }
}

// 处理返回按钮点击（添加禁用防止重复点击）
function handleGoBack() {
    // 禁用按钮防止重复点击
    const backBtn = document.querySelector('.btn-goback');
    if (backBtn) {
        backBtn.style.pointerEvents = 'none';
        backBtn.style.opacity = '0.7';
        backBtn.textContent = '返回中...';
    }
    
    // 立即执行返回
    setTimeout(goBack, 50);
}

// 清理所有定时器
function clearAllTimers() {
    // 清理所有可能的定时器
    for (let i = 0; i <= 10000; i++) {
        clearTimeout(i);
        clearInterval(i);
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', async function() {
    // 检查用户登录状态
    sessionId = localStorage.getItem('session_id');
    if (!sessionId) {
        alert('请先登录');
        window.location.href = 'index.html';
        return;
    }

    // 获取当前用户信息
    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            headers: {
                'X-Session-Id': sessionId
            }
        });
        const data = await response.json();
        
        console.log('登录验证响应:', data); // 调试信息
        
        if (data.success && data.username) {
            currentUser = data.username;
            console.log('用户登录成功:', currentUser);
        } else if (data.error) {
            console.error('登录验证失败:', data);
            alert('登录状态已过期，请重新登录');
            localStorage.removeItem('session_id');
            window.location.href = 'index.html';
            return;
        } else {
            console.error('未知的响应格式:', data);
            alert('获取用户信息失败，请重新登录');
            localStorage.removeItem('session_id');
            window.location.href = 'index.html';
            return;
        }
    } catch (error) {
        console.error('获取用户信息失败:', error);
        alert('网络错误，请检查后端服务是否运行');
        window.location.href = 'index.html';
        return;
    }

    // 初始化标签切换
    initTabs();

    // 加载健康档案
    await loadUserRecords();
    
    // 显示通知权限提示（若未授权）
    try {
        if ('Notification' in window) {
            console.log('通知权限状态:', Notification.permission);
            if (Notification.permission !== 'granted') {
                const banner = document.getElementById('notification-permission-banner');
                if (banner) banner.style.display = 'flex';
            } else {
                console.log('通知权限已授权');
            }
        } else {
            console.log('浏览器不支持通知');
        }
    } catch (e) {
        console.error('检查通知权限失败:', e);
    }

    // 加载初始数据（确保顺序）
    await loadMedications();
    await loadIntakeRecords();
    await loadReminders();
    loadStats();

    // 设置当前日期时间
    const now = new Date();
    const dateTimeInput = document.querySelector('input[name="taken_at"]');
    if (dateTimeInput) {
        dateTimeInput.value = now.toISOString().slice(0, 16);
    }

    const dateInput = document.querySelector('input[name="start_date"]');
    if (dateInput) {
        dateInput.value = now.toISOString().slice(0, 10);
    }
});

// 标签切换
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault(); // 阻止默认行为
            const tabName = this.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // 更新标签样式
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // 更新内容显示
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // 加载对应数据
    switch(tabName) {
        case 'medications':
            loadMedications();
            break;
        case 'reminders':
            loadReminders();
            break;
        case 'records':
            loadIntakeRecords();
            break;
        case 'analysis':
            // AI分析需要手动触发
            break;
        case 'stats':
            loadStats();
            break;
    }
}

// ==================== 健康档案功能 ====================

async function loadUserRecords() {
    try {
        const response = await fetch(`${API_BASE}/records?username=${currentUser}`, {
            headers: {
                'X-Session-Id': sessionId
            }
        });
        const data = await response.json();
        
        if (data.success || data.records) {
            userRecords = data.records || [];
            // 选择默认档案：优先使用后端的 active_record_id；
            // 若不存在，则自动选择第一个档案作为默认档案（确保一定有档案被选中）
            let selectedId = data.active_record_id || null;
            
            if (!selectedId && Array.isArray(userRecords) && userRecords.length > 0) {
                // 有档案但没有活跃档案标记，则选择第一个档案
                selectedId = userRecords[0].record_id;  // 修复：使用 record_id 而不是 id
            }
            
            if (selectedId) {
                currentRecordFilter = selectedId;
                console.log('已选择默认档案:', selectedId);
            }
            updateRecordSelectors();
            // 同步下拉选择器的选中值
            const recordFilter = document.getElementById('record-filter');
            if (recordFilter && currentRecordFilter) {
                recordFilter.value = currentRecordFilter;
            }
        }
    } catch (error) {
        console.error('加载档案失败:', error);
    }
}

function updateRecordSelectors() {
    console.log('更新档案选择器，档案数量:', userRecords.length);

    // 更新筛选下拉框
    const recordFilter = document.getElementById('record-filter');
    if (recordFilter) {
        if (userRecords.length === 0) {
            recordFilter.innerHTML = '<option value="">暂无健康档案</option>';
        } else {
            const options = userRecords.map(record =>
                `<option value="${record.record_id}">${record.name || '未命名档案'}</option>`  // 修复：使用 record_id
            ).join('');
            recordFilter.innerHTML = '<option value="">选择健康档案...</option>' + options;
        }
        console.log('已更新档案筛选下拉框');
        // 若已存在当前筛选档案，则让下拉框选中它
        if (currentRecordFilter) {
            recordFilter.value = currentRecordFilter;
        }
    } else {
        console.error('找不到record-filter元素');
    }
}

function filterByRecord() {
    const recordFilter = document.getElementById('record-filter');
    currentRecordFilter = recordFilter.value || null;
    
    console.log('档案筛选：', currentRecordFilter);  // 调试信息
    
    // 重新加载所有数据以应用筛选
    loadMedications();
    loadIntakeRecords();
    loadReminders();  // 也重新加载提醒
    loadStats();
    
    // 提示用户当前筛选状态
    if (currentRecordFilter) {
        const record = userRecords.find(r => r.record_id === currentRecordFilter);  // 修复：使用 record_id
        if (record) {
            console.log('选中档案：', record);  // 调试信息
            showSuccess(`已切换到档案：${record.name || '未命名'}`);
        }
    } else {
        showSuccess('已清除档案筛选');
    }
}

// ==================== 用药记录管理 ====================

async function loadMedications(status = null) {
    try {
        // 未选择档案时，不加载全部，提示用户先选择档案，避免“显示所有记录”的误解
        if (!currentRecordFilter) {
            const container = document.getElementById('medications-list');
            if (container) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📋</div>
                        <p>请选择一个健康档案以查看对应的用药记录</p>
                    </div>
                `;
            }
            return;
        }

        let url = `${API_BASE}/medications?username=${currentUser}`;
        if (status) url += `&status=${status}`;
        url += `&record_id=${currentRecordFilter}`;  // 传递档案ID到后端（此时必定存在）
        
        console.log('加载用药记录，URL:', url);  // 调试信息
        
        const response = await fetch(url);
        const data = await response.json();

        console.log('用药记录响应:', data);  // 调试信息

        if (data.success) {
            medications = data.medications;  // 后端已经筛选过了
            console.log('加载到用药数量:', medications.length);  // 调试信息
            
            renderMedications(medications);
            // 更新选择器
            updateMedicationSelectors();
        } else {
            showError('加载用药记录失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

function renderMedications(meds) {
    const container = document.getElementById('medications-list');
    
    // 额外保险：在前端再次过滤，确保只显示当前档案的用药
    const filteredMeds = currentRecordFilter 
        ? meds.filter(m => m.record_id === currentRecordFilter)
        : meds;
    
    console.log('渲染用药记录：', {
        '全部数量': meds.length,
        '当前档案': currentRecordFilter,
        '过滤后数量': filteredMeds.length
    });
    
    if (filteredMeds.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">💊</div>
                <p>还没有用药记录</p>
                ${currentRecordFilter ? 
                    '<p style="color: #666; font-size: 14px;">请先为选中的档案添加用药记录</p>' :
                    '<p style="color: #666; font-size: 14px;">请先选择健康档案，然后添加用药记录</p>'
                }
            </div>
        `;
        return;
    }

    container.innerHTML = filteredMeds.map(med => {
        // 查找关联的档案信息
        const record = med.record_id ? userRecords.find(r => r.record_id === med.record_id) : null;  // 修复：使用 record_id
        const recordInfo = record ? `${record.name || '未命名'}` : '个人用药';
        
        return `
        <div class="medication-card">
            <div class="medication-header">
                <div>
                    <h3 class="medication-title">
                        ${med.name}
                        <span class="medication-category">${med.category || '西药'}</span>
                    </h3>
                    <div style="margin-top: 5px;">
                        <span class="status-badge status-${med.status}">${getStatusText(med.status)}</span>
                        ${med.record_id ? `<span style="margin-left: 8px; color: #666; font-size: 13px;">📋 ${recordInfo}</span>` : ''}
                    </div>
                </div>
            </div>
            <div class="medication-info">
                <div class="info-item">
                    <span class="info-label">剂量：</span>
                    <span>${med.dosage || '未设置'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">频率：</span>
                    <span>${med.frequency || '未设置'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">疗程：</span>
                    <span>${med.duration || '未设置'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">开始日期：</span>
                    <span>${formatDate(med.start_date)}</span>
                </div>
                ${med.prescribing_doctor ? `
                <div class="info-item">
                    <span class="info-label">医生：</span>
                    <span>${med.prescribing_doctor}</span>
                </div>
                ` : ''}
                ${med.notes ? `
                <div class="info-item" style="grid-column: 1 / -1;">
                    <span class="info-label">备注：</span>
                    <span>${med.notes}</span>
                </div>
                ` : ''}
            </div>
            <div class="medication-actions">
                ${med.status === 'active' ? `
                    <button type="button" class="btn btn-small btn-success" onclick="recordIntakeQuick('${med.id}', '${med.name}')">✅ 记录服药</button>
                ` : ''}
                <button type="button" class="btn btn-small btn-primary" onclick="editMedication('${med.id}')">✏️ 编辑</button>
                ${med.status === 'active' ? `
                    <button type="button" class="btn btn-small btn-warning" onclick="updateMedicationStatus('${med.id}', 'completed')">✔️ 标记完成</button>
                    <button type="button" class="btn btn-small btn-danger" onclick="updateMedicationStatus('${med.id}', 'stopped')">⏹️ 停用</button>
                ` : ''}
                <button type="button" class="btn btn-small btn-danger" onclick="deleteMedication('${med.id}')">🗑️ 删除</button>
            </div>
        </div>
        `;
    }).join('');
}

function getStatusText(status) {
    const statusMap = {
        'active': '使用中',
        'completed': '已完成',
        'stopped': '已停用'
    };
    return statusMap[status] || status;
}

function filterMedications(status) {
    // 确保当前已选择档案时才允许过滤
    if (!currentRecordFilter) {
        showError('请先选择健康档案');
        return;
    }
    
    if (status === 'all') {
        loadMedications();
    } else {
        loadMedications(status);
    }
}

function showAddMedicationModal() {
    if (!currentRecordFilter) {
        showError('请先选择健康档案，然后再添加用药');
        return;
    }

    const record = userRecords.find(r => r.record_id === currentRecordFilter);  // 修复：使用 record_id
    const recordName = record ? (record.name || '未命名档案') : '未知档案';

    // 显示当前选择的档案
    const modal = document.getElementById('add-medication-modal');
    const header = modal.querySelector('.modal-header h2');
    if (header) {
        header.textContent = `为 ${recordName} 添加用药`;
    }

    document.getElementById('add-medication-modal').classList.add('active');
    document.getElementById('add-medication-form').reset();

    // 设置开始日期为今天
    const today = new Date().toISOString().slice(0, 10);
    const startDateInput = document.querySelector('input[name="start_date"]');
    if (startDateInput) {
        startDateInput.value = today;
    }
}

function editMedication(medicationId) {
    const medication = medications.find(m => m.id === medicationId);
    if (!medication) {
        showError('未找到该用药记录');
        return;
    }
    
    // 简单实现：提示用户可以删除后重新添加
    if (confirm(`编辑功能即将推出。\n\n当前药品：${medication.name}\n\n是否要删除此记录后重新添加？`)) {
        deleteMedication(medicationId);
    }
}

async function addMedication(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    const medication = {
        name: formData.get('name'),
        dosage: formData.get('dosage'),
        frequency: formData.get('frequency'),
        duration: formData.get('duration'),
        start_date: formData.get('start_date'),
        category: formData.get('category'),
        prescribing_doctor: formData.get('prescribing_doctor'),
        notes: formData.get('notes'),
        record_id: currentRecordFilter || ''  // 使用当前筛选的档案ID
    };

    try {
        const response = await fetch(`${API_BASE}/medications`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: currentUser,
                medication: medication
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('添加成功');
            closeModal('add-medication-modal');
            loadMedications();
        } else {
            showError('添加失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

async function updateMedicationStatus(medicationId, status) {
    if (!confirm(`确定要${getStatusText(status)}吗？`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/medications/${medicationId}?username=${currentUser}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: currentUser,
                medication: { status: status }
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('状态更新成功');
            loadMedications();
        } else {
            showError('更新失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

async function deleteMedication(medicationId) {
    if (!confirm('确定要删除这条用药记录吗？')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/medications/${medicationId}?username=${currentUser}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('删除成功');
            loadMedications();
        } else {
            showError('删除失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

// ==================== 服药提醒管理 ====================

async function loadReminders() {
    try {
        let url = `${API_BASE}/medications/reminders?username=${currentUser}`;
        if (currentRecordFilter) {
            url += `&record_id=${currentRecordFilter}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            reminders = data.reminders;
            renderReminders(reminders);
            console.log('加载到提醒:', reminders.length, '个');

            // 如果有提醒且通知已授权，启动检查
            if (reminders.length > 0 && Notification.permission === 'granted') {
                console.log('启动提醒检查');
                startReminderCheck();
            } else if (reminders.length > 0) {
                console.log('提醒存在但通知未授权:', Notification.permission);
            }
        } else {
            showError('加载提醒失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

function renderReminders(rems) {
    const container = document.getElementById('reminders-list');
    
    if (rems.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⏰</div>
                <p>还没有设置提醒</p>
                ${currentRecordFilter ? 
                    '<p style="color: #666; font-size: 14px;">请先为选中的档案添加用药记录，然后设置提醒</p>' :
                    '<p style="color: #666; font-size: 14px;">请先选择健康档案，然后添加提醒</p>'
                }
                <button type="button" class="btn btn-primary" onclick="showAddReminderModal()">添加第一个提醒</button>
            </div>
        `;
        return;
    }

    container.innerHTML = rems.map(rem => {
        let scheduleText = '';
        const times = Array.isArray(rem.times) ? rem.times : (rem.time ? [rem.time] : ['未设置']);
        const timeText = times.join(', ');
        
        if (rem.reminder_type === 'daily') {
            scheduleText = '每天';
        } else if (rem.reminder_type === 'interval') {
            scheduleText = `每${rem.interval_days || 1}天`;
        } else if (rem.reminder_type === 'custom') {
            scheduleText = Array.isArray(rem.custom_schedule) ? rem.custom_schedule.join(', ') : '自定义';
        } else {
            // 兼容旧格式
            scheduleText = Array.isArray(rem.days) ? rem.days.join(', ') : (rem.days || '每天');
        }
        
        return `
        <div class="reminder-card">
            <div class="reminder-info">
                <div class="reminder-time">⏰ ${timeText}</div>
                <div class="reminder-name">${rem.medication_name}</div>
                <div class="reminder-days">📅 ${scheduleText}</div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <label class="toggle-switch">
                    <input type="checkbox" ${rem.enabled ? 'checked' : ''} 
                           onchange="toggleReminder('${rem.id}', this.checked)">
                    <span class="toggle-slider"></span>
                </label>
                <button type="button" class="btn btn-small btn-danger" onclick="deleteReminder('${rem.id}')">删除</button>
            </div>
        </div>
        `;
    }).join('');
}

function showAddReminderModal() {
    // 确保已选择档案
    if (!currentRecordFilter) {
        showError('请先选择健康档案，然后再添加提醒');
        return;
    }
    
    // 先加载用药列表到选择器
    updateMedicationSelectors();
    
    // 重置提醒表单
    document.getElementById('add-reminder-form').reset();
    
    // 重要：清除times-container中的所有旧输入，重新初始化
    const timesContainer = document.getElementById('times-container');
    if (timesContainer) {
        // 清空所有子元素
        timesContainer.innerHTML = '';
        // 重新添加第一个时间输入框
        const firstTimeInput = document.createElement('div');
        firstTimeInput.style.display = 'flex';
        firstTimeInput.style.gap = '10px';
        firstTimeInput.style.marginBottom = '10px';
        firstTimeInput.innerHTML = `
            <input type="time" class="form-input time-input" value="08:00" required>
        `;
        timesContainer.appendChild(firstTimeInput);
    }
    
    // 重置提醒类型
    document.getElementById('reminder-type-select').value = 'daily';
    updateReminderFields();
    
    document.getElementById('add-reminder-modal').classList.add('active');
}

function updateMedicationSelectors() {
    // medications已经是后端筛选过的当前档案的用药
    const activeMeds = medications.filter(m => m.status === 'active');
    
    const reminderSelect = document.getElementById('reminder-medication-select');
    const intakeSelect = document.getElementById('intake-medication-select');
    
    const options = activeMeds.map(med => 
        `<option value="${med.id}">${med.name} (${med.dosage || '未设置剂量'})</option>`
    ).join('');

    if (reminderSelect) {
        reminderSelect.innerHTML = '<option value="">请选择</option>' + options;
    }
    if (intakeSelect) {
        intakeSelect.innerHTML = '<option value="">请选择</option>' + options;
    }
}

// 增强的提醒功能
function updateReminderFields() {
    const type = document.getElementById('reminder-type-select').value;
    const intervalGroup = document.getElementById('interval-group');
    const customGroup = document.getElementById('custom-schedule-group');
    
    // 隐藏所有可选字段
    intervalGroup.style.display = 'none';
    customGroup.style.display = 'none';
    
    // 根据类型显示对应字段
    if (type === 'interval') {
        intervalGroup.style.display = 'block';
    } else if (type === 'custom') {
        customGroup.style.display = 'block';
    }
}

function addTimeInput() {
    const container = document.getElementById('times-container');
    const newDiv = document.createElement('div');
    newDiv.style.display = 'flex';
    newDiv.style.gap = '10px';
    newDiv.style.marginBottom = '10px';
    newDiv.innerHTML = `
        <input type="time" class="form-input time-input" required>
        <button type="button" class="btn btn-small btn-danger" onclick="removeTimeInput(this)">删除</button>
    `;
    container.appendChild(newDiv);
}

function removeTimeInput(button) {
    const container = document.getElementById('times-container');
    if (container.children.length > 1) {
        button.parentElement.remove();
    } else {
        showError('至少保留一个提醒时间');
    }
}

async function addReminder(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    const medicationId = formData.get('medication_id');
    const medication = medications.find(m => m.id === medicationId);
    const reminderType = formData.get('reminder_type');
    
    // 收集所有时间输入
    const timeInputs = document.querySelectorAll('.time-input');
    const times = Array.from(timeInputs).map(input => input.value).filter(t => t);
    
    if (times.length === 0) {
        showError('请至少添加一个提醒时间');
        return;
    }
    
    const reminder = {
        medication_id: medicationId,
        medication_name: medication ? medication.name : '',
        reminder_type: reminderType,
        times: times,
        enabled: true
    };
    
    // 根据类型添加额外参数
    if (reminderType === 'interval') {
        reminder.interval_days = parseInt(formData.get('interval_days')) || 1;
    } else if (reminderType === 'custom') {
        const customDays = Array.from(document.querySelectorAll('input[name="custom_day"]:checked'))
            .map(cb => cb.value);
        if (customDays.length === 0) {
            showError('请至少选择一个星期');
            return;
        }
        reminder.custom_schedule = customDays;
    }

    try {
        const response = await fetch(`${API_BASE}/medications/reminders`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: currentUser,
                reminder: reminder
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('提醒添加成功');
            closeModal('add-reminder-modal');
            loadReminders();
        } else {
            showError('添加失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

async function toggleReminder(reminderId, enabled) {
    try {
        const response = await fetch(`${API_BASE}/medications/reminders/${reminderId}?username=${currentUser}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: currentUser,
                reminder: { enabled: enabled }
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess(enabled ? '提醒已启用' : '提醒已禁用');
        } else {
            showError('更新失败: ' + data.message);
            loadReminders(); // 重新加载以恢复状态
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
        loadReminders();
    }
}

async function deleteReminder(reminderId) {
    if (!confirm('确定要删除这个提醒吗？')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/medications/reminders/${reminderId}?username=${currentUser}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('删除成功');
            loadReminders();
        } else {
            showError('删除失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

// ==================== 服药记录管理 ====================

async function loadIntakeRecords() {
    try {
        let url = `${API_BASE}/medications/intake-records?username=${currentUser}`;
        if (currentRecordFilter) {
            url += `&record_id=${currentRecordFilter}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            intakeRecords = data.records;  // 后端已经筛选过了
            renderIntakeRecords(intakeRecords);
        } else {
            showError('加载服药记录失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

function renderIntakeRecords(records) {
    const container = document.getElementById('records-list');
    
    if (records.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📝</div>
                <p>还没有服药记录</p>
                <button type="button" class="btn btn-primary" onclick="showRecordIntakeModal()">记录第一次服药</button>
            </div>
        `;
        return;
    }

    container.innerHTML = records.map(record => `
        <div class="medication-card">
            <div class="medication-info">
                <div class="info-item">
                    <span class="info-label">药品：</span>
                    <span>${record.medication_name}</span>
                </div>
                ${record.record_name ? `
                <div class="info-item">
                    <span class="info-label">服药人：</span>
                    <span>${record.record_name}</span>
                </div>` : ''}
                <div class="info-item">
                    <span class="info-label">剂量：</span>
                    <span>${record.dosage || '未记录'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">服药时间：</span>
                    <span>${formatDateTime(record.taken_at)}</span>
                </div>
                ${record.notes ? `
                <div class="info-item" style="grid-column: 1 / -1;">
                    <span class="info-label">备注：</span>
                    <span>${record.notes}</span>
                </div>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function showRecordIntakeModal() {
    updateMedicationSelectors();
    document.getElementById('record-intake-modal').classList.add('active');
    document.getElementById('record-intake-form').reset();
    
    // 设置当前时间
    const now = new Date();
    document.querySelector('input[name="taken_at"]').value = now.toISOString().slice(0, 16);
}

async function recordIntake(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    const medicationId = formData.get('medication_id');
    const medication = medications.find(m => m.id === medicationId);
    const associatedRecord = medication && medication.record_id ? (userRecords.find(r => r.record_id === medication.record_id) || null) : null;
    
    const intake = {
        medication_id: medicationId,
        medication_name: medication ? medication.name : '',
        taken_at: formData.get('taken_at'),
        dosage: formData.get('dosage') || (medication ? medication.dosage : ''),
        notes: formData.get('notes'),
        // 传递档案信息
        record_id: medication ? (medication.record_id || '') : '',
        record_name: associatedRecord ? (associatedRecord.name || '') : ''
    };

    try {
        const response = await fetch(`${API_BASE}/medications/intake-records`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: currentUser,
                intake: intake
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('服药记录已保存');
            closeModal('record-intake-modal');
            loadIntakeRecords();
            loadStats(); // 更新统计
        } else {
            showError('保存失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

async function recordIntakeQuick(medicationId, medicationName) {
    const medication = medications.find(m => m.id === medicationId);
    const associatedRecord = medication && medication.record_id ? (userRecords.find(r => r.record_id === medication.record_id) || null) : null;

    const intake = {
        medication_id: medicationId,
        medication_name: medicationName,
        taken_at: new Date().toISOString(),
        dosage: '',
        notes: '',
        record_id: medication ? (medication.record_id || '') : '',
        record_name: associatedRecord ? (associatedRecord.name || '') : ''
    };

    try {
        const response = await fetch(`${API_BASE}/medications/intake-records`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: currentUser,
                intake: intake
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('服药已记录');
            loadStats(); // 更新统计
        } else {
            showError('记录失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

// ==================== AI分析 ====================

async function performAIAnalysis() {
    const container = document.getElementById('analysis-result');
    container.innerHTML = '<div class="loading">正在进行AI分析</div>';

    try {
        // 只分析当前档案的活跃用药（medications已经是后端筛选过的了）
        const medsToAnalyze = medications.filter(m => m.status === 'active');

        if (medsToAnalyze.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>当前档案没有活跃的用药记录</p>
                    <p style="color: #666; font-size: 14px;">请先添加用药记录，状态设置为"使用中"</p>
                </div>
            `;
            return;
        }

        const response = await fetch(`${API_BASE}/medications/ai-analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: currentUser,
                medications: medsToAnalyze
            })
        });

        const data = await response.json();

        if (data.success) {
            renderAIAnalysis(data.analysis);
        } else {
            showError('AI分析失败: ' + data.message);
            container.innerHTML = `<div class="empty-state"><p>分析失败: ${data.message}</p></div>`;
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
        container.innerHTML = `<div class="empty-state"><p>网络错误: ${error.message}</p></div>`;
    }
}

function renderAIAnalysis(analysis) {
    const container = document.getElementById('analysis-result');
    
    let html = `
        <div class="analysis-section">
            <h3 class="analysis-title">📊 总体评估</h3>
            <p>${analysis.summary || '暂无评估'}</p>
        </div>
    `;

    // 药物相互作用
    if (analysis.interactions && analysis.interactions.length > 0) {
        html += `
            <div class="analysis-section">
                <h3 class="analysis-title">⚠️ 药物相互作用</h3>
                ${analysis.interactions.map(interaction => `
                    <div class="interaction-item">
                        <div style="margin-bottom: 8px;">
                            <strong>${interaction.drug1}</strong> ↔️ <strong>${interaction.drug2}</strong>
                            <span class="severity-${(interaction.severity || '').toLowerCase() === '高' ? 'high' : (interaction.severity || '').toLowerCase() === '中' ? 'medium' : 'low'}">
                                (${interaction.severity || '未知'})
                            </span>
                        </div>
                        <div>${interaction.description || ''}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // 安全警告
    if (analysis.warnings && analysis.warnings.length > 0) {
        html += `
            <div class="analysis-section">
                <h3 class="analysis-title">🚨 安全警告</h3>
                ${analysis.warnings.map(warning => `
                    <div class="warning-item">
                        <div style="margin-bottom: 8px;">
                            <strong>${warning.type || '警告'}</strong>
                            <span class="severity-${(warning.severity || '').toLowerCase() === '高' ? 'high' : (warning.severity || '').toLowerCase() === '中' ? 'medium' : 'low'}">
                                (${warning.severity || '未知'})
                            </span>
                        </div>
                        <div>${warning.description || ''}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // 用药建议
    if (analysis.suggestions && analysis.suggestions.length > 0) {
        html += `
            <div class="analysis-section">
                <h3 class="analysis-title">💡 用药建议</h3>
                ${analysis.suggestions.map(suggestion => `
                    <div class="suggestion-item">
                        ${typeof suggestion === 'string' ? suggestion : suggestion.description || suggestion.text || ''}
                    </div>
                `).join('')}
            </div>
        `;
    }

    container.innerHTML = html;
}

// ==================== 用药统计 ====================

async function loadStats() {
    try {
        let url = `${API_BASE}/medications/adherence-stats?username=${currentUser}&days=7`;
        if (currentRecordFilter) {
            url += `&record_id=${currentRecordFilter}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            renderStats(data);
        } else {
            showError('加载统计失败: ' + data.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

function renderStats(stats) {
    const container = document.getElementById('stats-content');
    
    const adherenceColor = stats.adherence_rate >= 80 ? 'var(--success-color)' : 
                           stats.adherence_rate >= 60 ? 'var(--warning-color)' : 
                           'var(--danger-color)';
    
    container.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">用药种类</div>
                <div class="stat-value">${stats.total_medications}</div>
                <div class="stat-label">种</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">应服次数</div>
                <div class="stat-value">${stats.total_doses_expected}</div>
                <div class="stat-label">次</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">已服次数</div>
                <div class="stat-value">${stats.total_doses_taken}</div>
                <div class="stat-label">次</div>
            </div>
            <div class="stat-card" style="background: ${adherenceColor};">
                <div class="stat-label">依从性</div>
                <div class="stat-value">${stats.adherence_rate}%</div>
                <div class="stat-label">近${stats.days}天</div>
            </div>
        </div>
        
        <div class="analysis-section">
            <h3 class="analysis-title">📈 依从性评价</h3>
            <p>
                ${stats.adherence_rate >= 80 ? 
                    '太棒了！您的用药依从性很高，请继续保持规律用药！' : 
                    stats.adherence_rate >= 60 ?
                    '您的用药依从性一般，建议设置更多提醒，按时服药。' :
                    '您的用药依从性较低，请务必按医嘱规律服药，这对治疗效果很重要。'
                }
            </p>
        </div>
    `;
}

// ==================== 通知权限管理 ====================

let notificationCheckInterval = null;

function requestNotificationPermission() {
    if (!('Notification' in window)) {
        showError('抱歉，您的浏览器不支持桌面通知');
        return;
    }
    
    if (Notification.permission === 'granted') {
        showSuccess('通知权限已开启');
        const banner = document.getElementById('notification-permission-banner');
        if (banner) banner.style.display = 'none';
        
        // 启动提醒检查
        startReminderCheck();
        return;
    }
    
    if (Notification.permission === 'denied') {
        alert('⚠️ 通知权限已被禁止\n\n请在浏览器设置中手动开启：\n1. 点击地址栏左侧的锁图标\n2. 找到"通知"选项\n3. 改为"允许"');
        return;
    }
    
    // 请求权限
    Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
            showSuccess('✅ 通知权限已开启！您将收到按时服药提醒');
            const banner = document.getElementById('notification-permission-banner');
            if (banner) banner.style.display = 'none';
            
            // 测试通知
            try {
                new Notification('💊 用药提醒已开启', {
                    body: '我们会在设定的时间提醒您服药',
                    icon: '/favicon.ico'
                });
            } catch (e) {
                console.error('发送测试通知失败:', e);
            }
            
            // 启动提醒检查
            startReminderCheck();
        } else {
            showError('未获得通知权限，将无法收到服药提醒');
        }
    }).catch(error => {
        console.error('请求通知权限失败:', error);
        showError('请求通知权限失败');
    });
}

function startReminderCheck() {
    // 清除旧的定时器
    if (notificationCheckInterval) {
        clearInterval(notificationCheckInterval);
        notificationCheckInterval = null;
    }

    // 如果没有提醒或未选择档案，不启动检查
    if (!reminders || reminders.length === 0 || !currentRecordFilter) {
        console.log('无需启动提醒检查');
        return;
    }

    console.log('启动服药提醒检查');

    // 立即检查一次（测试用）
    setTimeout(() => {
        console.log('立即检查提醒...');
        checkReminders();
    }, 1000);

    // 每分钟检查一次
    notificationCheckInterval = setInterval(() => {
        console.log('定时检查提醒...');
        checkReminders();
    }, 60000);

    console.log('服药提醒检查已启动');
}

function checkReminders() {
    if (!reminders || reminders.length === 0) {
        console.log('无提醒数据，跳过检查');
        return;
    }

    console.log('检查提醒，当前提醒数量:', reminders.length);

    const now = new Date();
    const currentTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const today = now.toISOString().slice(0, 10);
    const dayOfWeek = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][now.getDay()];

    console.log('当前时间:', currentTime, '星期:', dayOfWeek);

    reminders.forEach(reminder => {
        if (!reminder.enabled) {
            console.log('提醒未启用:', reminder.medication_name);
            return;
        }
        
        const times = Array.isArray(reminder.times) ? reminder.times : [reminder.time || '08:00'];
        
        times.forEach(time => {
            console.log(`检查提醒: ${reminder.medication_name} - 设定时间:${time}, 当前时间:${currentTime}`);

            if (time !== currentTime) {
                console.log('时间不匹配，跳过');
                return;
            }

            // 检查是否应该在今天提醒
            let shouldRemind = false;

            if (reminder.reminder_type === 'daily') {
                shouldRemind = true;
                console.log('每日提醒，允许提醒');
            } else if (reminder.reminder_type === 'interval') {
                // 间隔天数提醒
                const intervalDays = reminder.interval_days || 1;
                const createdDate = new Date(reminder.created_at);
                const daysDiff = Math.floor((now - createdDate) / (1000 * 60 * 60 * 24));
                shouldRemind = daysDiff % intervalDays === 0;
                console.log(`间隔提醒: ${intervalDays}天, 已创建${daysDiff}天, 应该提醒:${shouldRemind}`);
            } else if (reminder.reminder_type === 'custom') {
                // 自定义星期提醒
                const customSchedule = reminder.custom_schedule || [];
                shouldRemind = customSchedule.includes(dayOfWeek);
                console.log(`自定义提醒: ${customSchedule.join(',')}, 今天:${dayOfWeek}, 应该提醒:${shouldRemind}`);
            }

            if (!shouldRemind) {
                console.log('今天不需要提醒');
                return;
            }

            // 检查今天这个时间是否已经提醒过
            const lastRemindedKey = `last_reminded_${reminder.id}_${time}_${today}`;
            const alreadyReminded = localStorage.getItem(lastRemindedKey);
            if (alreadyReminded) {
                console.log('今天已经提醒过了');
                return; // 今天这个时间已经提醒过了
            }

            console.log('满足条件，发送提醒通知');
            // 发送提醒
            sendMedicationNotification(reminder);

            // 记录已提醒
            localStorage.setItem(lastRemindedKey, 'true');
        });
    });
}

function sendMedicationNotification(reminder) {
    if (Notification.permission !== 'granted') {
        console.error('通知权限未授予，无法发送提醒');
        return;
    }

    const title = '💊 服药提醒';
    const options = {
        body: `该服用 ${reminder.medication_name} 了`,
        icon: '/favicon.ico',
        badge: '/favicon.ico',
        tag: `med-${reminder.id}`,
        requireInteraction: true,
        silent: false
    };

    console.log('准备发送通知:', title, options);

    try {
        const notification = new Notification(title, options);
        console.log('通知已创建');

        notification.onclick = function() {
            console.log('通知被点击');
            window.focus();
            // 切换到服药记录标签
            switchTab('records');
            notification.close();
        };

        // 播放提示音（使用更简单的音频）
        try {
            // 使用系统提示音或简短的音频数据
            const audio = new Audio();
            audio.volume = 0.5;
            // 使用一个简短的提示音
            audio.src = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVqzn77BdGAg+ltryxHYpBSuBzvLZiTYIGmm98OScTAoNUKXi8LZjHAU5kdXzzn0vBSh+zPLaizsKE127';
            audio.play().then(() => {
                console.log('提示音播放成功');
            }).catch((e) => {
                console.log('提示音播放失败:', e);
            });
        } catch (e) {
            console.log('音频播放错误:', e);
        }

        console.log(`✅ 已发送提醒: ${reminder.medication_name}`);

        // 5秒后自动关闭通知
        setTimeout(() => {
            notification.close();
        }, 5000);

    } catch (error) {
        console.error('发送通知失败:', error);
        // 备用方案：显示页面内通知
        showSuccess(`💊 服药提醒：该服用 ${reminder.medication_name} 了！`);
    }
}

// ==================== 工具函数 ====================

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function formatDate(dateString) {
    if (!dateString) return '未设置';
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN');
}

function formatDateTime(dateTimeString) {
    if (!dateTimeString) return '未知';
    const date = new Date(dateTimeString);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function showSuccess(message) {
    alert('✅ ' + message);
}

function showError(message) {
    alert('❌ ' + message);
    console.error(message);
}

// 点击模态框外部关闭
window.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('active');
    }
});

// ==================== 药品拍照识别功能 ====================

let cameraStream = null;  // 相机流
let recognizedMedications = [];  // 存储识别到的药品列表

// 触发照片上传
function triggerPhotoUpload() {
    const fileInput = document.getElementById('photo-upload-input');
    fileInput.click();
    
    fileInput.onchange = async function(e) {
        const file = e.target.files[0];
        if (file) {
            await recognizeMedicationFromFile(file);
        }
    };
}

// 启动相机拍照
async function startCameraCapture() {
    try {
        const modal = document.getElementById('camera-capture-modal');
        modal.classList.add('active');
        
        const video = document.getElementById('camera-video');
        
        // 请求相机权限
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' }  // 后摄像头
        });
        
        video.srcObject = cameraStream;
        video.play();
    } catch (error) {
        showError('无法打开相机: ' + error.message);
        closeCameraCapture();
    }
}

// 关闭相机
function closeCameraCapture() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    document.getElementById('camera-capture-modal').classList.remove('active');
}

// 拍照
async function captureMedicationPhoto() {
    try {
        const video = document.getElementById('camera-video');
        const canvas = document.getElementById('camera-canvas');
        const ctx = canvas.getContext('2d');
        
        // 设置canvas大小与视频相同
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // 绘制视频帧到canvas
        ctx.drawImage(video, 0, 0);
        
        // 转换为Blob
        canvas.toBlob(async (blob) => {
            await recognizeMedicationFromFile(blob);
            closeCameraCapture();
        }, 'image/jpeg', 0.9);
        
    } catch (error) {
        showError('拍照失败: ' + error.message);
    }
}

// 识别药品（从文件）
async function recognizeMedicationFromFile(file) {
    try {
        // 显示加载状态
        const preview = document.getElementById('medication-preview');
        const statusDiv = document.getElementById('recognition-status');
        const photoImg = document.getElementById('medication-photo-preview');
        const listDiv = document.getElementById('recognized-medications-list');
        
        // 显示图片
        const reader = new FileReader();
        reader.onload = function(e) {
            photoImg.src = e.target.result;
            preview.style.display = 'block';
            statusDiv.innerHTML = '🔄 正在识别药品信息...';
            listDiv.style.display = 'none';
        };
        reader.readAsDataURL(file);
        
        // 转换为Base64用于上传
        const base64Data = await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.readAsDataURL(file);
        });
        
        // 调用后端API识别药品
        const response = await fetch(`${API_BASE}/medications/recognize-photo`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                image: base64Data
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // 获取识别的药品列表
            const medicationList = data.medication_list || [];
            
            if (medicationList.length > 0) {
                recognizedMedications = medicationList;
                statusDiv.innerHTML = `✅ 成功识别 ${medicationList.length} 个药品，请检查并编辑信息`;
                
                // 显示识别结果列表
                displayRecognizedMedications(medicationList);
                listDiv.style.display = 'block';
            } else {
                statusDiv.innerHTML = '⚠️ 未识别到药品信息，请手动填写';
                listDiv.style.display = 'none';
                recognizedMedications = [];
            }
        } else {
            statusDiv.innerHTML = `❌ 识别失败: ${data.message}`;
            listDiv.style.display = 'none';
            recognizedMedications = [];
            console.error('识别失败:', data);
        }
        
    } catch (error) {
        console.error('识别请求失败:', error);
        const statusDiv = document.getElementById('recognition-status');
        statusDiv.innerHTML = `❌ 识别错误: ${error.message}`;
        const listDiv = document.getElementById('recognized-medications-list');
        listDiv.style.display = 'none';
        recognizedMedications = [];
        showError('识别请求失败: ' + error.message);
    }
}

// 显示识别结果
function displayRecognizedMedications(medicationList) {
    const container = document.getElementById('medications-cards');
    container.innerHTML = '';
    
    medicationList.forEach((med, index) => {
        const card = document.createElement('div');
        card.style.cssText = `
            background: #f9f9f9;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 10px;
        `;
        
        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h4 style="margin: 0; color: #333;">药品 ${index + 1}</h4>
                <button type="button" class="btn btn-small btn-danger" onclick="deleteMedicationFromList(${index})" style="padding: 4px 8px; font-size: 12px;">
                    🗑️ 删除
                </button>
            </div>
            
            <div style="display: grid; gap: 8px;">
                <div>
                    <label style="font-size: 12px; color: #666;">药品名称:</label>
                    <input type="text" value="${med.name || ''}" onchange="updateRecognizedMed(${index}, 'name', this.value)" 
                           style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px;" required>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div>
                        <label style="font-size: 12px; color: #666;">剂量:</label>
                        <input type="text" value="${med.dosage || ''}" onchange="updateRecognizedMed(${index}, 'dosage', this.value)" 
                               placeholder="如：100mg" style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px;">
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666;">频率:</label>
                        <input type="text" value="${med.frequency || ''}" onchange="updateRecognizedMed(${index}, 'frequency', this.value)" 
                               placeholder="如：每日3次" style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px;">
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div>
                        <label style="font-size: 12px; color: #666;">疗程:</label>
                        <input type="text" value="${med.duration || ''}" onchange="updateRecognizedMed(${index}, 'duration', this.value)" 
                               placeholder="如：7天" style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px;">
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666;">分类:</label>
                        <select onchange="updateRecognizedMed(${index}, 'category', this.value)" 
                                style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px;">
                            <option value="西药" ${med.category === '西药' ? 'selected' : ''}>西药</option>
                            <option value="中药" ${med.category === '中药' ? 'selected' : ''}>中药</option>
                            <option value="营养品" ${med.category === '营养品' ? 'selected' : ''}>营养品</option>
                        </select>
                    </div>
                </div>
                
                <div>
                    <label style="font-size: 12px; color: #666;">备注:</label>
                    <input type="text" value="${med.notes || ''}" onchange="updateRecognizedMed(${index}, 'notes', this.value)" 
                           placeholder="如：饭后服用" style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px;">
                </div>
            </div>
        `;
        
        container.appendChild(card);
    });
}

// 更新识别结果中的药品信息
function updateRecognizedMed(index, field, value) {
    if (recognizedMedications[index]) {
        recognizedMedications[index][field] = value;
    }
}

// 从列表中删除药品
function deleteMedicationFromList(index) {
    recognizedMedications.splice(index, 1);
    if (recognizedMedications.length > 0) {
        displayRecognizedMedications(recognizedMedications);
    } else {
        document.getElementById('recognized-medications-list').style.display = 'none';
        clearRecognitionResults();
    }
}

// 清空识别结果
function clearRecognitionResults() {
    recognizedMedications = [];
    document.getElementById('medication-preview').style.display = 'none';
    document.getElementById('recognized-medications-list').style.display = 'none';
    document.getElementById('recognition-status').innerHTML = '';
    document.getElementById('medications-cards').innerHTML = '';
}

// 批量保存识别的药品
async function saveBatchMedications() {
    if (recognizedMedications.length === 0) {
        showError('没有要保存的药品');
        return;
    }
    
    // 验证所有药品都有名称
    const invalidMeds = recognizedMedications.filter(med => !med.name || med.name.trim() === '');
    if (invalidMeds.length > 0) {
        showError('请填写所有药品的名称');
        return;
    }
    
    // 验证是否选择了档案
    if (!currentRecordFilter) {
        showError('请先选择健康档案');
        return;
    }
    
    console.log('开始批量保存...');
    console.log('当前档案ID:', currentRecordFilter);
    console.log('要保存的药品数:', recognizedMedications.length);
    console.log('药品列表:', recognizedMedications);
    
    try {
        let successCount = 0;
        let failureCount = 0;
        const errors = [];
        
        // 逐个保存药品
        for (let i = 0; i < recognizedMedications.length; i++) {
            const med = recognizedMedications[i];
            try {
                console.log(`保存药品 ${i + 1}:`, med.name);
                
                const saveData = {
                    username: currentUser,  // 添加用户名
                    medication: {
                        name: med.name,
                        dosage: med.dosage || '',
                        frequency: med.frequency || '',
                        duration: med.duration || '',
                        category: med.category || '西药',
                        notes: med.notes || '',
                        record_id: currentRecordFilter
                    }
                };
                
                console.log('发送请求数据:', saveData);
                
                const response = await fetch(`${API_BASE}/medications`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(saveData)
                });
                
                console.log(`药品 ${i + 1} 响应状态:`, response.status);
                
                const data = await response.json();
                console.log(`药品 ${i + 1} 响应数据:`, data);
                
                if (data.success) {
                    successCount++;
                    console.log(`✅ 药品 ${i + 1} (${med.name}) 保存成功`);
                } else {
                    failureCount++;
                    const errMsg = `${med.name}: ${data.message || '未知错误'}`;
                    errors.push(errMsg);
                    console.error(`❌ 药品 ${i + 1} 保存失败:`, data.message);
                }
            } catch (err) {
                console.error(`❌ 保存药品 ${i + 1} 异常:`, err);
                failureCount++;
                errors.push(`${med.name}: ${err.message}`);
            }
        }
        
        console.log('批量保存完成，成功:', successCount, '失败:', failureCount);
        
        if (successCount > 0) {
            let message = `✅ 成功保存 ${successCount} 个药品`;
            if (failureCount > 0) {
                message += `，失败 ${failureCount} 个`;
                if (errors.length > 0) {
                    message += `\n\n失败详情：\n${errors.join('\n')}`;
                }
            }
            showSuccess(message);
            recognizedMedications = [];
            document.getElementById('medication-preview').style.display = 'none';
            document.getElementById('recognized-medications-list').style.display = 'none';
            loadMedications();  // 刷新列表
        } else {
            let message = '保存失败，请重试';
            if (errors.length > 0) {
                message += `\n\n失败原因：\n${errors.join('\n')}`;
            }
            showError(message);
        }
    } catch (error) {
        console.error('批量保存异常:', error);
        showError('批量保存失败: ' + error.message);
    }
}

// ==================== 页面性能优化 ====================

// 页面卸载前清理资源，加速返回首页
window.addEventListener('beforeunload', function() {
    // 快速清理所有数据
    medications = null;
    reminders = null;
    intakeRecords = null;
    userRecords = null;
    currentUser = null;
}, false);

// 页面隐藏时清理（用户离开标签页时）
window.addEventListener('pagehide', function() {
    // 清理定时器
    clearAllTimers();
}, false);
