// AI医疗功能集成模块

class MedicalAI {
    constructor() {
        this.isConnected = false;
        this.baseURL = 'http://localhost:5000/api';
        this._healthTimer = null;
        this.init();
    }

    async init() {
        try {
            // 检查后端服务连接
            console.log('正在连接医疗AI后端服务...');
            await this.connect();
        } catch (error) {
            console.error('❌ 医疗AI服务连接失败:', error);
            console.log('🔄 将使用备用模拟功能');
            this.isConnected = false;
        }

        // 若未连接则周期性重试，连上后自动停止
        if (!this.isConnected && !this._healthTimer) {
            this._healthTimer = setInterval(async () => {
                const ok = await this.connect();
                if (ok && this._healthTimer) {
                    clearInterval(this._healthTimer);
                    this._healthTimer = null;
                }
            }, 5000);
        }
    }

    // 主动健康检查并建立连接
    async connect() {
        try {
            console.log('🔄 正在连接医疗AI服务...');
            const response = await fetch(`${this.baseURL}/health`, { 
                cache: 'no-store'
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            console.log('✅ 医疗AI服务连接成功:', data.service);
            console.log('🤖 使用模型:', data.model);
            console.log('📊 服务状态:', data.status);
            this.isConnected = true;
            return true;
        } catch (e) {
            console.warn('❌ 连接失败:', e.message);
            this.isConnected = false;
            try { window.showNotification && window.showNotification('AI服务连接失败，请检查后端是否运行', 'error'); } catch(_) {}
            return false;
        }
    }

    // 在每次真实调用前确保已连接，避免初始化时误判
    async ensureConnected() {
        if (this.isConnected) return true;
        const ok = await this.connect();
        return ok;
    }

    // 知识页专用AI搜索（药品/疾病提示词）
    async knowledgeSearch(query, kind = 'auto') {
        try {
            if (await this.ensureConnected()) {
                const sessionId = (window.getActiveSessionId && window.getActiveSessionId()) || (window.sessionId) || null;
                const response = await fetch(`${this.baseURL}/knowledge-search`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(sessionId ? { 'X-Session-Id': sessionId } : {})
                    },
                    body: JSON.stringify({ query, kind })
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const result = await response.json();
                return result;
            }
        } catch (e) {
            console.warn('知识AI搜索失败', e);
        }
        return { success: false, message: '搜索失败' };
    }

    // 疾病风险预测
    async predictDiseaseRisk(patientVitals) {
        if (!this.isConnected) {
            return this.getFallbackDiseaseRisk(patientVitals);
        }

        try {
            // 构建患者生命体征数据
            const vitalsData = {
                age: patientVitals.age || 35,
                gender: patientVitals.gender || 'male',
                blood_pressure_systolic: patientVitals.systolic || 120,
                blood_pressure_diastolic: patientVitals.diastolic || 80,
                heart_rate: patientVitals.heartRate || 72,
                temperature: patientVitals.temperature || 36.5,
                symptoms: patientVitals.symptoms || [],
                medical_history: patientVitals.history || []
            };

            // 这里可以调用真实的医疗AI API
            // const result = await mcp_pyhealth_disease_risk({ patient_vitals: vitalsData });
            
            // 暂时使用模拟数据
            return this.getFallbackDiseaseRisk(vitalsData);
            
        } catch (error) {
            console.error('疾病风险预测失败:', error);
            return this.getFallbackDiseaseRisk(patientVitals);
        }
    }

    // 药物推荐
    async recommendDrugs(patientHistory) {
        if (!this.isConnected) {
            return this.getFallbackDrugRecommendation(patientHistory);
        }

        try {
            // 构建患者病史数据
            const historyData = {
                patient_id: patientHistory.patientId || 'unknown',
                age: patientHistory.age || 35,
                diagnoses: patientHistory.diagnoses || [],
                current_medications: patientHistory.currentMeds || [],
                allergies: patientHistory.allergies || [],
                symptoms: patientHistory.symptoms || [],
                vital_signs: patientHistory.vitals || {}
            };

            // 这里可以调用真实的医疗AI API
            // const result = await mcp_pyhealth_drug_recommendation({ patient_history: historyData });
            
            // 暂时使用模拟数据
            return this.getFallbackDrugRecommendation(historyData);
            
        } catch (error) {
            console.error('药物推荐失败:', error);
            return this.getFallbackDrugRecommendation(patientHistory);
        }
    }

    // 再入院风险预测
    async predictReadmissionRisk(patientData) {
        if (!this.isConnected) {
            return this.getFallbackReadmissionRisk(patientData);
        }

        try {
            // 构建患者数据
            const readmissionData = {
                patient_id: patientData.patientId || 'unknown',
                admission_date: patientData.admissionDate || new Date().toISOString(),
                primary_diagnosis: patientData.primaryDiagnosis || '',
                secondary_diagnoses: patientData.secondaryDiagnoses || [],
                procedures: patientData.procedures || [],
                length_of_stay: patientData.lengthOfStay || 3,
                age: patientData.age || 35,
                comorbidities: patientData.comorbidities || []
            };

            // 这里可以调用真实的医疗AI API
            // const result = await mcp_pyhealth_readmission_risk({ patient_data: readmissionData });
            
            // 暂时使用模拟数据
            return this.getFallbackReadmissionRisk(readmissionData);
            
        } catch (error) {
            console.error('再入院风险预测失败:', error);
            return this.getFallbackReadmissionRisk(patientData);
        }
    }

    // 住院时长预测
    async predictHospitalDuration(admissionDetails) {
        if (!this.isConnected) {
            return this.getFallbackDurationPrediction(admissionDetails);
        }

        try {
            // 构建入院详情数据
            const durationData = {
                patient_age: admissionDetails.age || 35,
                primary_diagnosis: admissionDetails.diagnosis || '',
                admission_type: admissionDetails.admissionType || 'emergency',
                vital_signs: admissionDetails.vitals || {},
                lab_results: admissionDetails.labResults || {},
                comorbidities: admissionDetails.comorbidities || [],
                severity_score: admissionDetails.severityScore || 5
            };

            // 这里可以调用真实的医疗AI API
            // const result = await mcp_pyhealth_duration_prediction({ admission_details: durationData });
            
            // 暂时使用模拟数据
            return this.getFallbackDurationPrediction(durationData);
            
        } catch (error) {
            console.error('住院时长预测失败:', error);
            return this.getFallbackDurationPrediction(admissionDetails);
        }
    }

    // 症状分析和智能诊断
    async analyzeSymptoms(symptoms) {
        try {
            const symptomList = Array.isArray(symptoms) ? symptoms : [symptoms];
            const symptomText = symptomList.join(', ');
            const sessionId = (window.getActiveSessionId && window.getActiveSessionId()) || (window.sessionId) || null;
            const activeRecordId = (window.getActiveRecordId && window.getActiveRecordId()) || (window.currentUser && window.currentUser.active_record_id) || null;
            
            if (await this.ensureConnected()) {
                // 调用真实的AI后端服务
                console.log('🔍 正在调用Qwen AI进行症状分析...');
                const response = await fetch(`${this.baseURL}/analyze-symptoms`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(sessionId ? { 'X-Session-Id': sessionId } : {})
                    },
                    body: JSON.stringify({
                        symptoms: symptomText,
                        patient_info: { active_record_id: activeRecordId }
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const result = await response.json();
                
                if (result.error) {
                    throw new Error(result.message || '后端分析失败');
                }

                console.log('✅ Qwen AI分析完成');
                return result;
                
            } else {
                // 使用备用分析功能
                console.log('🔄 使用备用分析功能');
                return this.getFallbackSymptomAnalysis(symptomList);
            }
            
        } catch (error) {
            console.error('❌ 症状分析失败:', error);
            // 返回备用分析结果
            return this.getFallbackSymptomAnalysis(symptomList);
        }
    }

    // 生成诊断建议
    generateDiagnosisAdvice(symptoms, riskData) {
        const adviceMap = {
            '头痛': '可能原因：压力、睡眠不足、血压异常。建议充分休息，监测血压。',
            '发烧': '身体自然防御反应。多喝水，适当休息，体温过高时及时就医。',
            '咳嗽': '可能由感染、过敏等引起。保持室内湿度，避免刺激性物质。',
            '胸闷': '可能涉及心肺功能。建议避免剧烈运动，必要时心电图检查。',
            '腹痛': '可能涉及消化系统。注意饮食，症状持续应排查器质性病变。'
        };

        let advice = '';
        symptoms.forEach(symptom => {
            for (let key in adviceMap) {
                if (symptom.includes(key)) {
                    advice += adviceMap[key] + ' ';
                    break;
                }
            }
        });

        return advice || '建议详细记录症状，及时咨询医疗专业人士。';
    }

    // 生成医疗建议
    generateRecommendations(symptoms) {
        const recommendations = [
            '记录症状的发生时间、持续时间和严重程度',
            '保持充足的休息和睡眠',
            '注意饮食健康，多喝水'
        ];

        // 根据症状添加特定建议
        if (symptoms.some(s => s.includes('发烧') || s.includes('发热'))) {
            recommendations.push('监测体温变化');
            recommendations.push('如体温超过38.5℃，可服用退热药');
        }

        if (symptoms.some(s => s.includes('咳嗽'))) {
            recommendations.push('避免吸烟和刺激性气体');
            recommendations.push('保持室内空气湿润');
        }

        if (symptoms.some(s => s.includes('胸闷') || s.includes('心慌'))) {
            recommendations.push('避免剧烈运动');
            recommendations.push('保持心情平静');
        }

        recommendations.push('如症状持续或加重，请及时就医');
        
        return recommendations;
    }

    // 评估紧急程度
    assessUrgencyLevel(symptoms) {
        const emergencySymptoms = ['胸痛', '呼吸困难', '剧烈头痛', '高烧', '意识障碍'];
        const urgentSymptoms = ['持续发烧', '严重咳嗽', '腹痛', '呕吐'];
        
        for (let symptom of symptoms) {
            if (emergencySymptoms.some(emergency => symptom.includes(emergency))) {
                return {
                    level: 'emergency',
                    message: '症状可能较为严重，建议立即就医',
                    color: '#e74c3c'
                };
            }
        }

        for (let symptom of symptoms) {
            if (urgentSymptoms.some(urgent => symptom.includes(urgent))) {
                return {
                    level: 'urgent',
                    message: '建议尽快就医检查',
                    color: '#f39c12'
                };
            }
        }

        return {
            level: 'normal',
            message: '症状相对较轻，可观察并适当治疗',
            color: '#27ae60'
        };
    }

    // 健康咨询AI对话
    async healthConsultation(question, conversationContext = []) {
        try {
            const sessionId = (window.getActiveSessionId && window.getActiveSessionId()) || (window.sessionId) || null;
            const activeRecordId = (window.getActiveRecordId && window.getActiveRecordId()) || (window.currentUser && window.currentUser.active_record_id) || null;
            if (await this.ensureConnected()) {
                console.log('💬 正在调用Qwen AI进行健康咨询...');
                const response = await fetch(`${this.baseURL}/health-consultation`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(sessionId ? { 'X-Session-Id': sessionId } : {})
                    },
                    body: JSON.stringify({
                        question: question,
                        context: conversationContext,
                        active_record_id: activeRecordId
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const result = await response.json();
                
                if (result.error) {
                    throw new Error(result.message || '咨询服务失败');
                }

                console.log('✅ Qwen AI健康咨询完成');
                return result;
                
            } else {
                // 使用备用咨询功能
                return this.getFallbackConsultation(question);
            }
            
        } catch (error) {
            console.error('❌ 健康咨询失败:', error);
            return this.getFallbackConsultation(question);
        }
    }

    // 药物推荐API调用
    async recommendDrugs(patientHistory) {
        try {
            const sessionId = (window.getActiveSessionId && window.getActiveSessionId()) || (window.sessionId) || null;
            const activeRecordId = (window.getActiveRecordId && window.getActiveRecordId()) || (window.currentUser && window.currentUser.active_record_id) || null;
            if (await this.ensureConnected()) {
                console.log('💊 正在调用Qwen AI进行药物推荐...');
                const symptoms = Array.isArray(patientHistory.symptoms) 
                    ? patientHistory.symptoms.join(', ')
                    : (patientHistory.symptoms || '未指定症状');
                    
                const response = await fetch(`${this.baseURL}/drug-recommendation`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(sessionId ? { 'X-Session-Id': sessionId } : {})
                    },
                    body: JSON.stringify({
                        symptoms: symptoms,
                        medical_history: { ...patientHistory, active_record_id: activeRecordId }
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const result = await response.json();
                
                if (result.error) {
                    throw new Error(result.message || '药物推荐失败');
                }

                console.log('✅ Qwen AI药物推荐完成');
                return result;
                
            } else {
                return this.getFallbackDrugRecommendation(patientHistory);
            }
            
        } catch (error) {
            console.error('❌ 药物推荐失败:', error);
            return this.getFallbackDrugRecommendation(patientHistory);
        }
    }

    // 备用症状分析
    getFallbackSymptomAnalysis(symptomList) {
        const symptomText = symptomList.join(', ');
        const urgency = this.assessUrgencyLevel(symptomList);
        const recommendations = this.generateRecommendations(symptomList);
        const diagnosis = this.generateDiagnosisAdvice(symptomList, {});
        
        return {
            success: true,
            diagnosis_advice: diagnosis,
            urgency_level: urgency,
            recommendations: recommendations,
            risk_assessment: {
                risk_level: urgency.level === 'emergency' ? '高风险' : '中等风险',
                risk_score: urgency.level === 'emergency' ? 70 : 30
            },
            source: 'fallback'
        };
    }

    // 备用健康咨询
    getFallbackConsultation(question) {
        let response = '';
        
        if (question.includes('头痛') || question.includes('头疼')) {
            response = '头痛可能由多种原因引起，包括压力、睡眠不足、脱水等。建议您充分休息，保证充足睡眠，多喝水。如果头痛持续或加重，请及时就医。';
        } else if (question.includes('发烧') || question.includes('发热')) {
            response = '发热是身体的自然免疫反应。建议多喝水，适当休息，可以用温水擦拭身体降温。如果体温超过38.5℃，可考虑服用退热药物。持续高热请及时就医。';
        } else if (question.includes('咳嗽')) {
            response = '咳嗽可能是呼吸系统的防御反应。建议保持室内空气湿润，避免刺激性气体，多喝温水。如果咳嗽伴有其他症状或持续时间较长，建议就医检查。';
        } else {
            response = '感谢您的咨询。建议您详细记录症状的发生时间、持续时间和严重程度，这有助于医生的诊断。如果症状持续或加重，请及时就医咨询专业医生。';
        }
        
        return {
            success: true,
            response: response,
            source: 'fallback'
        };
    }

    // 备用数据生成函数
    getFallbackDiseaseRisk(patientVitals) {
        const riskFactors = [];
        let riskScore = 0;

        // 模拟风险评估逻辑
        if (patientVitals.age > 60) {
            riskFactors.push('年龄因素');
            riskScore += 15;
        }
        
        if (patientVitals.blood_pressure_systolic > 140) {
            riskFactors.push('高血压');
            riskScore += 20;
        }
        
        if (patientVitals.symptoms && patientVitals.symptoms.length > 2) {
            riskFactors.push('多重症状');
            riskScore += 10;
        }

        return {
            risk_score: Math.min(riskScore + Math.random() * 10, 100),
            risk_level: riskScore > 30 ? '高风险' : riskScore > 15 ? '中等风险' : '低风险',
            risk_factors: riskFactors,
            recommendations: [
                '定期健康检查',
                '保持健康生活方式',
                '按医嘱服药'
            ]
        };
    }

    getFallbackDrugRecommendation(patientHistory) {
        const commonDrugs = [
            {
                name: '对乙酰氨基酚',
                dosage: '500mg',
                frequency: '每6-8小时一次',
                indication: '退热止痛',
                precautions: '肝功能不全者慎用'
            },
            {
                name: '布洛芬',
                dosage: '400mg',
                frequency: '每8小时一次',
                indication: '消炎止痛',
                precautions: '胃溃疡患者禁用'
            }
        ];

        return {
            recommended_drugs: commonDrugs.slice(0, Math.floor(Math.random() * 2) + 1),
            warnings: [
                '请在医生指导下使用',
                '注意药物相互作用',
                '遵循说明书用药'
            ],
            follow_up: '用药后请观察效果，如有不适及时停药并就医'
        };
    }

    getFallbackReadmissionRisk(patientData) {
        let riskPercentage = Math.random() * 30;
        
        // 根据患者数据调整风险
        if (patientData.age > 65) riskPercentage += 5;
        if (patientData.comorbidities && patientData.comorbidities.length > 2) riskPercentage += 8;
        if (patientData.length_of_stay > 7) riskPercentage += 3;

        return {
            risk_percentage: Math.min(riskPercentage, 100),
            risk_factors: [
                '年龄因素',
                '既往病史',
                '并发症情况'
            ],
            prevention_measures: [
                '严格按医嘱服药',
                '定期复查',
                '保持健康生活方式',
                '及时处理并发症'
            ]
        };
    }

    getFallbackDurationPrediction(admissionDetails) {
        let baseDays = 5;
        
        // 根据诊断调整天数
        if (admissionDetails.primary_diagnosis.includes('手术')) baseDays += 3;
        if (admissionDetails.severity_score > 7) baseDays += 2;
        if (admissionDetails.patient_age > 70) baseDays += 1;

        return {
            predicted_days: baseDays + Math.floor(Math.random() * 3),
            confidence_level: 0.75 + Math.random() * 0.2,
            factors: [
                '疾病严重程度',
                '患者年龄',
                '治疗响应',
                '并发症风险'
            ],
            discharge_criteria: [
                '生命体征稳定',
                '症状明显改善',
                '无严重并发症',
                '患者能够自理'
            ]
        };
    }
}

// 创建全局医疗AI实例
const medicalAI = new MedicalAI();

// 导出医疗AI功能供其他模块使用
window.MedicalAI = medicalAI;