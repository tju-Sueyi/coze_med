
// ================================
// 智能预问诊功能
// ================================

// 预问诊状态
let preConsultationState = {
    sessionId: null,
    chiefComplaint: '',
    questions: [],
    answers: {},
    currentQuestionIndex: 0,
    latestReportId: null  // 保存最新生成的报告ID
};

// 快速设置主诉
function setQuickComplaint(complaintText) {
    const input = document.getElementById('chief-complaint-input');
    if (input) {
        input.value = complaintText;
    }
}

// 开始预问诊
async function startPreConsultation() {
    const chiefComplaintInput = document.getElementById('chief-complaint-input');
    const chiefComplaint = chiefComplaintInput ? chiefComplaintInput.value.trim() : '';
    
    if (!chiefComplaint) {
        showNotification('请输入主要不适症状', 'warning');
        return;
    }
    
    // 获取患者基本信息
    const patientInfo = {
        name: currentUser?.name || '患者',
        age: currentUser?.age || '',
        gender: currentUser?.gender || ''
    };
    
    try {
        showNotification('AI正在为您生成问诊问题，请稍候...', 'info');
        
        const response = await fetch('http://localhost:5000/api/pre-consultation/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Username': sessionId ? (currentUser?.username || '') : ''
            },
            body: JSON.stringify({
                chief_complaint: chiefComplaint,
                patient_info: patientInfo
            })
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.message || '生成问诊问题失败');
        }
        
        // 保存问诊状态
        preConsultationState = {
            sessionId: data.session_id,
            chiefComplaint: chiefComplaint,
            questions: data.questions || [],
            answers: {},
            currentQuestionIndex: 0
        };
        
        // 切换到步骤2
        switchConsultationStep(2);
        
        // 渲染问题
        renderConsultationQuestions();
        
        showNotification('问诊问题已生成，请逐一回答', 'success');
        
    } catch (error) {
        console.error('开始预问诊失败:', error);
        showNotification('开始预问诊失败: ' + error.message, 'error');
    }
}

// 切换问诊步骤
function switchConsultationStep(stepNumber) {
    // 隐藏所有步骤
    document.querySelectorAll('.consultation-step').forEach(step => {
        step.classList.remove('active');
    });
    
    // 显示目标步骤
    const targetStep = document.getElementById('consultation-step-' + stepNumber);
    if (targetStep) {
        targetStep.classList.add('active');
    }
}

// 渲染问诊问题
function renderConsultationQuestions() {
    const container = document.getElementById('consultation-questions-container');
    if (!container || !preConsultationState.questions) return;
    
    const questions = preConsultationState.questions;
    
    let html = '';
    questions.forEach((q, index) => {
        const questionHtml = escapeHtml(q.question);
        const categoryHtml = escapeHtml(q.category || '一般问诊');
        
        html += `
            <div class="knowledge-card" style="padding: 20px; margin-bottom: 16px;">
                <div style="display: flex; align-items: start; gap: 12px; margin-bottom: 12px;">
                    <div style="background: linear-gradient(135deg, #0ea5e9, #0c4a6e); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-weight: 600;">${index + 1}</div>
                    <div style="flex: 1;">
                        <h4 style="margin: 0 0 4px 0; color: #1e293b; font-weight: 600;">${questionHtml}</h4>
                        <div style="font-size: 12px; color: #64748b;">
                            <i class="fas fa-tag"></i> ${categoryHtml}
                        </div>
                    </div>
                </div>
                <div class="question-input">
                    ${renderQuestionInput(q, index)}
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    updateConsultationProgress();
}

// 渲染问题输入框
function renderQuestionInput(question, index) {
    const qId = question.id;
    const questionText = escapeHtml(question.question);
    
    switch (question.type) {
        case 'text':
            return `<textarea id="answer-${qId}" class="input" rows="3" placeholder="请输入您的回答..." onchange="saveAnswer('${qId}', this.value, '${questionText}')"></textarea>`;
            
        case 'yes_no':
            return `
                <div style="display: flex; gap: 12px;">
                    <label class="chip" style="cursor: pointer; padding: 10px 20px;">
                        <input type="radio" name="answer-${qId}" value="是" onchange="saveAnswer('${qId}', '是', '${questionText}')" style="margin-right: 6px;"> 是
                    </label>
                    <label class="chip" style="cursor: pointer; padding: 10px 20px;">
                        <input type="radio" name="answer-${qId}" value="否" onchange="saveAnswer('${qId}', '否', '${questionText}')" style="margin-right: 6px;"> 否
                    </label>
                </div>
            `;
            
        case 'choice':
        case 'scale':
            const options = question.options || [];
            return `
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    ${options.map(opt => {
                        const optHtml = escapeHtml(opt);
                        return `
                            <label class="chip" style="cursor: pointer; padding: 10px 16px;">
                                <input type="radio" name="answer-${qId}" value="${optHtml}" onchange="saveAnswer('${qId}', '${optHtml}', '${questionText}')" style="margin-right: 6px;"> ${optHtml}
                            </label>
                        `;
                    }).join('')}
                </div>
            `;
            
        case 'multi_choice':
            const multiOptions = question.options || [];
            return `
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    ${multiOptions.map(opt => {
                        const optHtml = escapeHtml(opt);
                        return `
                            <label class="chip" style="cursor: pointer; padding: 10px 16px;">
                                <input type="checkbox" name="answer-${qId}" value="${optHtml}" onchange="saveMultiAnswer('${qId}', '${questionText}')" style="margin-right: 6px;"> ${optHtml}
                            </label>
                        `;
                    }).join('')}
                </div>
            `;
            
        default:
            return `<input type="text" id="answer-${qId}" class="input" placeholder="请输入您的回答..." onchange="saveAnswer('${qId}', this.value, '${questionText}')" />`;
    }
}

// 保存单选答案
function saveAnswer(questionId, answer, questionText) {
    preConsultationState.answers[questionId] = {
        question: questionText,
        answer: answer
    };
    updateConsultationProgress();
}

// 保存多选答案
function saveMultiAnswer(questionId, questionText) {
    const checkboxes = document.querySelectorAll(`input[name="answer-${questionId}"]:checked`);
    const answers = Array.from(checkboxes).map(cb => cb.value);
    
    preConsultationState.answers[questionId] = {
        question: questionText,
        answer: answers.join('、')
    };
    updateConsultationProgress();
}

// 更新问诊进度
function updateConsultationProgress() {
    const totalQuestions = preConsultationState.questions.length;
    const answeredQuestions = Object.keys(preConsultationState.answers).length;
    
    const progressText = document.getElementById('question-progress-text');
    const progressBar = document.getElementById('question-progress-bar');
    const submitBtn = document.getElementById('submit-consultation-btn');
    
    if (progressText) {
        progressText.textContent = `${answeredQuestions}/${totalQuestions}`;
    }
    
    if (progressBar) {
        const percentage = totalQuestions > 0 ? (answeredQuestions / totalQuestions * 100) : 0;
        progressBar.style.width = percentage + '%';
    }
    
    // 启用/禁用提交按钮
    if (submitBtn) {
        if (answeredQuestions >= totalQuestions) {
            submitBtn.disabled = false;
        } else {
            submitBtn.disabled = true;
        }
    }
}

// 返回步骤1
function backToStep1() {
    switchConsultationStep(1);
}

// 提交预问诊
async function submitPreConsultation() {
    const totalQuestions = preConsultationState.questions.length;
    const answeredQuestions = Object.keys(preConsultationState.answers).length;
    
    if (answeredQuestions < totalQuestions) {
        showNotification(`还有 ${totalQuestions - answeredQuestions} 个问题未回答`, 'warning');
        return;
    }
    
    try {
        showNotification('正在生成预问诊报告，请稍候...', 'info');
        
        const patientInfo = {
            name: currentUser?.name || '患者',
            age: currentUser?.age || '',
            gender: currentUser?.gender || ''
        };
        
        const response = await fetch('http://localhost:5000/api/pre-consultation/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Username': sessionId ? (currentUser?.username || '') : ''
            },
            body: JSON.stringify({
                session_id: preConsultationState.sessionId,
                chief_complaint: preConsultationState.chiefComplaint,
                answers: preConsultationState.answers,
                patient_info: patientInfo
            })
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.message || '提交预问诊失败');
        }
        
        // 保存report_id
        if (data.report_id) {
            preConsultationState.latestReportId = data.report_id;
        }
        
        // 显示报告
        displayConsultationReport(data.report, data.saved_to_record, data.report_id);
        
        // 切换到步骤3
        switchConsultationStep(3);
        
        showNotification(data.saved_to_record ? '预问诊报告已生成并保存到档案' : '预问诊报告已生成', 'success');
        
    } catch (error) {
        console.error('提交预问诊失败:', error);
        showNotification('提交预问诊失败: ' + error.message, 'error');
    }
}

// 显示问诊报告
function displayConsultationReport(report, savedToRecord, reportId = null) {
    const container = document.getElementById('consultation-report-container');
    if (!container) return;
    
    // 紧急程度颜色映射
    const urgencyColors = {
        '非紧急': '#10b981',
        '一般': '#3b82f6',
        '紧急': '#f59e0b',
        '危重': '#ef4444'
    };
    
    const urgencyColor = urgencyColors[report.urgency_level] || '#64748b';
    const urgencyLevel = escapeHtml(report.urgency_level);
    const summary = escapeHtml(report.summary);
    const doctorNotes = escapeHtml(report.doctor_notes || '无特殊备注');
    const department = escapeHtml(report.recommended_department);
    
    // 如果有报告ID，保存到状态
    if (reportId) {
        preConsultationState.latestReportId = reportId;
    }
    
    const html = `
        <div class="knowledge-card" style="padding: 24px; margin-bottom: 20px;">
            <!-- 报告标题 -->
            <div style="text-align: center; margin-bottom: 24px;">
                <h2 style="color: #1e293b; margin: 0 0 8px 0;">
                    <i class="fas fa-file-medical-alt"></i> 预问诊报告
                </h2>
                <div style="color: #64748b; font-size: 14px;">
                    生成时间: ${new Date().toLocaleString('zh-CN')}
                    ${savedToRecord ? '<span style="color: #10b981; margin-left: 12px;"><i class="fas fa-check-circle"></i> 已保存到档案</span>' : ''}
                </div>
            </div>
            
            <!-- 紧急程度标签 -->
            <div style="background: ${urgencyColor}; color: white; padding: 12px 20px; border-radius: 8px; text-align: center; font-weight: 600; margin-bottom: 20px;">
                <i class="fas fa-exclamation-circle"></i> 紧急程度: ${urgencyLevel}
            </div>
            
            <!-- 病情概述 -->
            <div style="margin-bottom: 20px;">
                <h3 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-bottom: 12px;">
                    <i class="fas fa-notes-medical"></i> 病情概述
                </h3>
                <p style="line-height: 1.6; color: #475569;">${summary}</p>
            </div>
            
            <!-- 关键信息 -->
            <div style="margin-bottom: 20px;">
                <h3 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-bottom: 12px;">
                    <i class="fas fa-list-ul"></i> 关键信息
                </h3>
                <ul style="line-height: 1.8; color: #475569;">
                    ${(report.key_points || []).map(point => `<li>${escapeHtml(point)}</li>`).join('')}
                </ul>
            </div>
            
            <!-- 初步诊断 -->
            <div style="margin-bottom: 20px;">
                <h3 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-bottom: 12px;">
                    <i class="fas fa-stethoscope"></i> 初步诊断考虑
                </h3>
                <ul style="line-height: 1.8; color: #475569;">
                    ${(report.preliminary_diagnosis || []).map(diagnosis => `<li>${escapeHtml(diagnosis)}</li>`).join('')}
                </ul>
            </div>
            
            <!-- 建议检查 -->
            <div style="margin-bottom: 20px;">
                <h3 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-bottom: 12px;">
                    <i class="fas fa-microscope"></i> 建议检查项目
                </h3>
                <ul style="line-height: 1.8; color: #475569;">
                    ${(report.recommended_tests || []).map(test => `<li>${escapeHtml(test)}</li>`).join('')}
                </ul>
            </div>
            
            <!-- 建议科室 -->
            <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border-left: 4px solid #3b82f6; margin-bottom: 20px;">
                <div style="font-weight: 600; color: #1e293b; margin-bottom: 8px;">
                    <i class="fas fa-hospital"></i> 建议就诊科室
                </div>
                <div style="font-size: 18px; color: #3b82f6; font-weight: 600;">
                    ${department}
                </div>
            </div>
            
            <!-- 医生备注 -->
            <div style="background: #fffbeb; padding: 16px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                <div style="font-weight: 600; color: #92400e; margin-bottom: 8px;">
                    <i class="fas fa-user-md"></i> 给医生的备注
                </div>
                <div style="color: #78350f; line-height: 1.6;">
                    ${doctorNotes}
                </div>
            </div>
        </div>
        
        <div class="notification" style="margin-top: 20px;">
            <div class="notification-content">
                <i class="fas fa-info-circle"></i>
                <div>
                    <strong>温馨提示：</strong>
                    <p style="margin: 5px 0 0;">本报告仅供参考，不能代替医生的专业诊断。建议您携带此报告前往医院就诊，以便医生更快了解您的病情。</p>
                </div>
            </div>
        </div>
        
        ${reportId && savedToRecord ? `
        <div class="knowledge-card" style="padding: 20px; margin-top: 20px; background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border: 2px solid #0ea5e9;">
            <div style="margin-bottom: 16px;">
                <h3 style="margin: 0 0 8px 0; color: #1e293b; display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-paper-plane" style="color: #0ea5e9;"></i> 
                    推送给医生
                </h3>
                <p style="margin: 0; color: #64748b; font-size: 14px;">将此报告推送给指定医生，方便医生提前了解您的病情</p>
            </div>
            
            <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                <input 
                    type="text" 
                    id="doctor-search-input" 
                    placeholder="搜索医生姓名或账号..." 
                    class="input" 
                    style="flex: 1; min-width: 200px; padding: 10px 14px; border: 2px solid #cbd5e1; border-radius: 8px;"
                    onkeyup="if(event.key === 'Enter') searchDoctors()"
                />
                <button class="btn btn-outline" onclick="searchDoctors()" style="padding: 10px 20px;">
                    <i class="fas fa-search"></i> 搜索
                </button>
            </div>
            
            <div id="doctor-search-results" style="margin-top: 16px; display: none;">
                <!-- 搜索结果将显示在这里 -->
            </div>
        </div>
        ` : ''}
    `;
    
    container.innerHTML = html;
}

// 重新开始问诊
function restartConsultation() {
    preConsultationState = {
        sessionId: null,
        chiefComplaint: '',
        questions: [],
        answers: {},
        currentQuestionIndex: 0
    };
    
    // 清空输入
    const input = document.getElementById('chief-complaint-input');
    if (input) input.value = '';
    
    // 返回步骤1
    switchConsultationStep(1);
}

// 查看所有报告
function viewAllReports() {
    if (!sessionId) {
        showNotification('请先登录以查看历史记录', 'warning');
        showLogin();
        return;
    }
    
    // 跳转到档案页面
    showPage('records');
}

// ================================
// 医生端功能：查看患者预问诊报告
// ================================

// 加载患者的预问诊报告（医生端）
async function loadPatientPreConsultation() {
    if (!sessionId || !currentUser) {
        showNotification('请先登录', 'warning');
        return;
    }
    
    try {
        showNotification('正在加载推送的预问诊报告...', 'info');
        
        const response = await fetch('http://localhost:5000/api/doctors/pre-consultation/reports', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Username': currentUser.username || ''
            }
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.message || '加载预问诊报告失败');
        }
        
        displayDoctorPreConsultationList(data.reports || []);
        
        if (data.reports && data.reports.length > 0) {
            showNotification(`已加载 ${data.reports.length} 份推送的预问诊报告`, 'success');
        } else {
            showNotification('暂无患者推送的预问诊报告', 'info');
        }
        
    } catch (error) {
        console.error('加载预问诊报告失败:', error);
        showNotification('加载预问诊报告失败: ' + error.message, 'error');
    }
}

// 显示预问诊报告列表（医生端）
function displayDoctorPreConsultationList(reports) {
    const container = document.getElementById('doctor-pre-consultation-display');
    if (!container) return;
    
    if (!reports || reports.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #94a3b8;">
                <i class="fas fa-inbox" style="font-size: 48px; margin-bottom: 12px; opacity: 0.3;"></i>
                <p>暂无患者推送的预问诊报告</p>
            </div>
        `;
        return;
    }
    
    // 紧急程度颜色映射
    const urgencyColors = {
        '非紧急': '#10b981',
        '一般': '#3b82f6',
        '紧急': '#f59e0b',
        '危重': '#ef4444'
    };
    
    const html = `
        <div style="display: grid; gap: 12px;">
            ${reports.map(report => {
                const urgencyColor = urgencyColors[report.urgency_level] || '#64748b';
                const urgencyLevel = escapeHtml(report.urgency_level || '一般');
                const chiefComplaint = escapeHtml(report.chief_complaint || '未提供');
                const patientName = escapeHtml(report.patient_name || '未知患者');
                const createdAt = new Date(report.created_at).toLocaleString('zh-CN');
                const pushedAt = new Date(report.pushed_at).toLocaleString('zh-CN');
                const pushId = report.push_id || '';
                const reportId = report.report_id || '';
                
                return `
                    <div class="knowledge-card" style="padding: 16px; transition: all 0.2s; border: 1px solid #e2e8f0;">
                        <div style="display: flex; align-items: start; justify-content: space-between; gap: 16px;">
                            <div style="flex: 1; cursor: pointer;" onclick="viewDoctorPreConsultationDetailByContent(${JSON.stringify(report.content).replace(/"/g, '&quot;')})">
                                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                                    <h4 style="margin: 0; color: #1e293b; font-weight: 600;">
                                        <i class="fas fa-user" style="color: #3b82f6;"></i> ${patientName}
                                    </h4>
                                    <span style="background: ${urgencyColor}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;">
                                        ${urgencyLevel}
                                    </span>
                                </div>
                                <div style="color: #64748b; font-size: 14px; margin-bottom: 4px;">
                                    <i class="fas fa-notes-medical"></i> 主诉：${chiefComplaint}
                                </div>
                                <div style="color: #94a3b8; font-size: 12px; display: flex; gap: 12px;">
                                    <span><i class="fas fa-clock"></i> 创建：${createdAt}</span>
                                    <span><i class="fas fa-paper-plane"></i> 推送：${pushedAt}</span>
                                </div>
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 8px;">
                                <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); fillEmrFromPreConsultationContent(${JSON.stringify(report.content).replace(/"/g, '&quot;')})" style="white-space: nowrap; padding: 6px 12px;">
                                    <i class="fas fa-arrow-right"></i> 填入病历
                                </button>
                                <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); deleteDoctorPreConsultationReport('${pushId}')" style="white-space: nowrap; padding: 6px 12px; color: #ef4444; border-color: #ef4444;">
                                    <i class="fas fa-trash"></i> 删除
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
    
    container.innerHTML = html;
}

// 查看预问诊报告详情（医生端）
async function viewDoctorPreConsultationDetail(reportId) {
    if (!sessionId || !currentUser) {
        showNotification('请先登录', 'warning');
        return;
    }
    
    try {
        showNotification('正在加载报告详情...', 'info');
        
        // 从当前用户的档案中获取报告详情
        const response = await fetch('http://localhost:5000/api/records', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Session-Id': sessionId
            }
        });
        
        const data = await response.json();
        
        if (!response.ok || data.error) {
            throw new Error(data.message || '获取报告详情失败');
        }
        
        // 查找对应的预问诊报告
        let reportContent = null;
        for (const record of (data.records || [])) {
            const reports = record.reports || [];
            const targetReport = reports.find(r => r.report_id === reportId && r.type === 'pre_consultation');
            if (targetReport) {
                reportContent = targetReport.content;
                break;
            }
        }
        
        if (!reportContent) {
            throw new Error('未找到该报告');
        }
        
        // 显示报告详情弹窗
        showPreConsultationDetailModal(reportContent);
        
    } catch (error) {
        console.error('查看报告详情失败:', error);
        showNotification('查看报告详情失败: ' + error.message, 'error');
    }
}

// 显示预问诊详情弹窗
function showPreConsultationDetailModal(content) {
    const report = content.report || {};
    const chiefComplaint = escapeHtml(content.chief_complaint || '未提供');
    const consultationText = escapeHtml(content.consultation_text || '');
    
    // 紧急程度颜色映射
    const urgencyColors = {
        '非紧急': '#10b981',
        '一般': '#3b82f6',
        '紧急': '#f59e0b',
        '危重': '#ef4444'
    };
    
    const urgencyColor = urgencyColors[report.urgency_level] || '#64748b';
    const urgencyLevel = escapeHtml(report.urgency_level || '一般');
    const summary = escapeHtml(report.summary || '');
    const department = escapeHtml(report.recommended_department || '');
    const doctorNotes = escapeHtml(report.doctor_notes || '');
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 800px; max-height: 90vh; overflow-y: auto;">
            <div class="modal-header">
                <h3><i class="fas fa-file-medical-alt"></i> 预问诊报告详情</h3>
                <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <!-- 主诉 -->
                <div style="margin-bottom: 20px; padding: 16px; background: #f8fafc; border-radius: 8px;">
                    <div style="font-weight: 600; color: #1e293b; margin-bottom: 8px;">
                        <i class="fas fa-notes-medical"></i> 患者主诉
                    </div>
                    <div style="color: #475569;">
                        ${chiefComplaint}
                    </div>
                </div>
                
                <!-- 紧急程度 -->
                <div style="background: ${urgencyColor}; color: white; padding: 12px; border-radius: 8px; text-align: center; font-weight: 600; margin-bottom: 20px;">
                    <i class="fas fa-exclamation-circle"></i> 紧急程度: ${urgencyLevel}
                </div>
                
                <!-- 病情概述 -->
                <div style="margin-bottom: 20px;">
                    <h4 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-bottom: 12px;">
                        <i class="fas fa-notes-medical"></i> 病情概述
                    </h4>
                    <p style="line-height: 1.6; color: #475569;">${summary}</p>
                </div>
                
                <!-- 关键信息 -->
                <div style="margin-bottom: 20px;">
                    <h4 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-bottom: 12px;">
                        <i class="fas fa-list-ul"></i> 关键信息
                    </h4>
                    <ul style="line-height: 1.8; color: #475569;">
                        ${(report.key_points || []).map(point => `<li>${escapeHtml(point)}</li>`).join('')}
                    </ul>
                </div>
                
                <!-- 初步诊断 -->
                <div style="margin-bottom: 20px;">
                    <h4 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-bottom: 12px;">
                        <i class="fas fa-stethoscope"></i> 初步诊断考虑
                    </h4>
                    <ul style="line-height: 1.8; color: #475569;">
                        ${(report.preliminary_diagnosis || []).map(diagnosis => `<li>${escapeHtml(diagnosis)}</li>`).join('')}
                    </ul>
                </div>
                
                <!-- 建议检查 -->
                <div style="margin-bottom: 20px;">
                    <h4 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-bottom: 12px;">
                        <i class="fas fa-microscope"></i> 建议检查项目
                    </h4>
                    <ul style="line-height: 1.8; color: #475569;">
                        ${(report.recommended_tests || []).map(test => `<li>${escapeHtml(test)}</li>`).join('')}
                    </ul>
                </div>
                
                <!-- 建议科室 -->
                <div style="background: #f8fafc; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                    <div style="font-weight: 600; color: #1e293b; margin-bottom: 8px;">
                        <i class="fas fa-hospital"></i> 建议就诊科室
                    </div>
                    <div style="font-size: 18px; color: #3b82f6; font-weight: 600;">
                        ${department}
                    </div>
                </div>
                
                <!-- 医生备注 -->
                <div style="background: #fffbeb; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                    <div style="font-weight: 600; color: #92400e; margin-bottom: 8px;">
                        <i class="fas fa-user-md"></i> 给医生的备注
                    </div>
                    <div style="color: #78350f; line-height: 1.6;">
                        ${doctorNotes}
                    </div>
                </div>
                
                <!-- 完整问诊记录 -->
                <div style="background: #f1f5f9; padding: 16px; border-radius: 8px;">
                    <div style="font-weight: 600; color: #1e293b; margin-bottom: 8px;">
                        <i class="fas fa-list"></i> 完整问诊记录
                    </div>
                    <pre style="white-space: pre-wrap; font-family: inherit; color: #475569; font-size: 14px; line-height: 1.6; margin: 0;">${consultationText}</pre>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-outline" onclick="this.closest('.modal').remove()">关闭</button>
                <button class="btn btn-primary" onclick="fillEmrFromPreConsultationContent(${JSON.stringify(content).replace(/"/g, '&quot;')}); this.closest('.modal').remove();">
                    <i class="fas fa-arrow-right"></i> 填入病历框
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

// 将预问诊信息填入病历输入框（通过report_id）
async function fillEmrFromPreConsultation(reportId) {
    if (!sessionId || !currentUser) {
        showNotification('请先登录', 'warning');
        return;
    }
    
    try {
        // 从当前用户的档案中获取报告详情
        const response = await fetch('http://localhost:5000/api/records', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Session-Id': sessionId
            }
        });
        
        const data = await response.json();
        
        if (!response.ok || data.error) {
            throw new Error(data.message || '获取报告详情失败');
        }
        
        // 查找对应的预问诊报告
        let reportContent = null;
        for (const record of (data.records || [])) {
            const reports = record.reports || [];
            const targetReport = reports.find(r => r.report_id === reportId && r.type === 'pre_consultation');
            if (targetReport) {
                reportContent = targetReport.content;
                break;
            }
        }
        
        if (!reportContent) {
            throw new Error('未找到该报告');
        }
        
        fillEmrFromPreConsultationContent(reportContent);
        
    } catch (error) {
        console.error('填入病历失败:', error);
        showNotification('填入病历失败: ' + error.message, 'error');
    }
}

// 将预问诊内容填入病历输入框（通过content对象）
function fillEmrFromPreConsultationContent(content) {
    const briefInput = document.getElementById('emr-brief-input');
    if (!briefInput) return;
    
    const chiefComplaint = content.chief_complaint || '';
    const consultationText = content.consultation_text || '';
    const report = content.report || {};
    
    // 构建简要信息
    let briefText = `【来自预问诊】\n`;
    briefText += `主诉：${chiefComplaint}\n\n`;
    
    if (report.key_points && report.key_points.length > 0) {
        briefText += `关键信息：\n`;
        report.key_points.forEach(point => {
            briefText += `- ${point}\n`;
        });
        briefText += `\n`;
    }
    
    if (report.preliminary_diagnosis && report.preliminary_diagnosis.length > 0) {
        briefText += `初步诊断考虑：${report.preliminary_diagnosis.join('、')}\n`;
    }
    
    briefInput.value = briefText;
    
    showNotification('已将预问诊信息填入病历输入框', 'success');
}

// ================================
// 患者端：搜索医生和推送报告
// ================================

// 搜索医生
async function searchDoctors() {
    const searchInput = document.getElementById('doctor-search-input');
    const resultsContainer = document.getElementById('doctor-search-results');
    
    if (!searchInput || !resultsContainer) return;
    
    const keyword = searchInput.value.trim();
    
    if (!keyword) {
        showNotification('请输入搜索关键词', 'warning');
        return;
    }
    
    try {
        resultsContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: #64748b;"><i class="fas fa-spinner fa-spin"></i> 搜索中...</div>';
        resultsContainer.style.display = 'block';
        
        const response = await fetch(`http://localhost:5000/api/doctors/search?keyword=${encodeURIComponent(keyword)}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.message || '搜索失败');
        }
        
        displayDoctorSearchResults(data.doctors || []);
        
    } catch (error) {
        console.error('搜索医生失败:', error);
        resultsContainer.innerHTML = `<div style="text-align: center; padding: 20px; color: #ef4444;"><i class="fas fa-exclamation-circle"></i> ${escapeHtml(error.message)}</div>`;
    }
}

// 显示医生搜索结果
function displayDoctorSearchResults(doctors) {
    const resultsContainer = document.getElementById('doctor-search-results');
    if (!resultsContainer) return;
    
    if (doctors.length === 0) {
        resultsContainer.innerHTML = `
            <div style="text-align: center; padding: 20px; color: #64748b;">
                <i class="fas fa-user-md" style="font-size: 2rem; margin-bottom: 8px; opacity: 0.5;"></i>
                <p>未找到匹配的医生</p>
            </div>
        `;
        return;
    }
    
    const html = `
        <div style="background: white; border-radius: 8px; padding: 12px; border: 1px solid #e2e8f0;">
            <h4 style="margin: 0 0 12px 0; color: #1e293b; font-size: 14px;">找到 ${doctors.length} 位医生</h4>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                ${doctors.map(doctor => `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #f8fafc; border-radius: 6px; border: 1px solid #e2e8f0;">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; color: #1e293b; margin-bottom: 4px;">
                                <i class="fas fa-user-md" style="color: #0ea5e9;"></i> ${escapeHtml(doctor.name)}
                            </div>
                            <div style="font-size: 13px; color: #64748b;">
                                账号：${escapeHtml(doctor.username)}
                            </div>
                        </div>
                        <button 
                            class="btn btn-primary btn-sm" 
                            onclick="pushReportToDoctor('${escapeHtml(doctor.username)}', '${escapeHtml(doctor.name)}')"
                            style="padding: 8px 16px; white-space: nowrap;"
                        >
                            <i class="fas fa-paper-plane"></i> 推送
                        </button>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    
    resultsContainer.innerHTML = html;
    resultsContainer.style.display = 'block';
}

// 推送报告给医生
async function pushReportToDoctor(doctorUsername, doctorName) {
    if (!sessionId) {
        showNotification('请先登录', 'warning');
        return;
    }
    
    const reportId = preConsultationState.latestReportId;
    
    if (!reportId) {
        showNotification('无法获取报告ID', 'error');
        return;
    }
    
    try {
        showNotification('正在推送报告...', 'info');
        
        const response = await fetch('http://localhost:5000/api/pre-consultation/push', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Username': currentUser?.username || ''
            },
            body: JSON.stringify({
                doctor_username: doctorUsername,
                report_id: reportId
            })
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.message || '推送失败');
        }
        
        showNotification(data.message || `已成功推送给 ${doctorName}`, 'success');
        
        // 清空搜索结果
        const resultsContainer = document.getElementById('doctor-search-results');
        if (resultsContainer) {
            resultsContainer.style.display = 'none';
        }
        
        const searchInput = document.getElementById('doctor-search-input');
        if (searchInput) {
            searchInput.value = '';
        }
        
    } catch (error) {
        console.error('推送报告失败:', error);
        showNotification('推送失败: ' + error.message, 'error');
    }
}

// ================================
// 医生端：删除推送的预问诊报告
// ================================

// 通过content对象直接查看报告详情（医生端）
function viewDoctorPreConsultationDetailByContent(content) {
    if (!content) {
        showNotification('无效的报告内容', 'error');
        return;
    }
    
    showPreConsultationDetailModal(content);
}

// 删除推送的预问诊报告（医生端）
async function deleteDoctorPreConsultationReport(pushId) {
    if (!sessionId || !currentUser) {
        showNotification('请先登录', 'warning');
        return;
    }
    
    if (!pushId) {
        showNotification('无效的报告ID', 'error');
        return;
    }
    
    if (!confirm('确定要删除这份预问诊报告吗？删除后将无法恢复。')) {
        return;
    }
    
    try {
        showNotification('正在删除...', 'info');
        
        const response = await fetch(`http://localhost:5000/api/doctors/pre-consultation/reports/${pushId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-Username': currentUser.username || ''
            }
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.message || '删除失败');
        }
        
        showNotification('已删除该报告', 'success');
        
        // 重新加载列表
        loadPatientPreConsultation();
        
    } catch (error) {
        console.error('删除报告失败:', error);
        showNotification('删除失败: ' + error.message, 'error');
    }
}

