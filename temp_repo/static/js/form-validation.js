/**
 * Sistema de Validação de Formulários - Sistema Olivion
 * Validações em tempo real com feedback visual
 */

class FormValidator {
    constructor() {
        this.rules = {
            username: {
                minLength: 3,
                maxLength: 50,
                pattern: /^[a-zA-Z0-9_-]+$/,
                required: true
            },
            password: {
                minLength: 6,
                maxLength: 128,
                pattern: /^(?=.*[A-Za-z])(?=.*\d)/,
                required: true
            },
            email: {
                pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                required: true
            },
            titulo: {
                minLength: 5,
                maxLength: 200,
                required: true
            },
            descricao: {
                minLength: 10,
                maxLength: 2000,
                required: true
            },
            ramal: {
                pattern: /^\d{3,6}$/,
                required: false
            },
            cdc: {
                maxLength: 50,
                required: false
            }
        };

        this.init();
    }

    init() {
        // Aguardar o DOM carregar
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.bindEvents());
        } else {
            this.bindEvents();
        }
    }

    bindEvents() {
        // Validação em tempo real para inputs
        document.querySelectorAll('input, textarea, select').forEach(field => {
            field.addEventListener('blur', (e) => this.validateField(e.target));
            field.addEventListener('input', (e) => this.clearErrors(e.target));
        });

        // Validação especial para upload de arquivos
        document.querySelectorAll('input[type="file"]').forEach(input => {
            input.addEventListener('change', (e) => this.validateFile(e.target));
        });

        // Validação em formulários submit
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                }
            });
        });

        // Força da senha em tempo real
        const passwordField = document.querySelector('input[name="password"]');
        if (passwordField) {
            passwordField.addEventListener('input', (e) => this.showPasswordStrength(e.target));
        }
    }

    validateField(field) {
        const name = field.name;
        const value = field.value.trim();
        const rule = this.rules[name];

        if (!rule) return true;

        const errors = [];

        // Validar campo obrigatório
        if (rule.required && !value) {
            errors.push(`${this.getFieldLabel(field)} é obrigatório`);
        }

        if (value) {
            // Validar comprimento mínimo
            if (rule.minLength && value.length < rule.minLength) {
                errors.push(`${this.getFieldLabel(field)} deve ter pelo menos ${rule.minLength} caracteres`);
            }

            // Validar comprimento máximo
            if (rule.maxLength && value.length > rule.maxLength) {
                errors.push(`${this.getFieldLabel(field)} não pode ter mais de ${rule.maxLength} caracteres`);
            }

            // Validar padrão
            if (rule.pattern && !rule.pattern.test(value)) {
                errors.push(this.getPatternErrorMessage(name));
            }
        }

        // Validações específicas
        if (name === 'usuario_setor') {
            this.checkComprasSetor(value, field.form);
        }

        this.showFieldErrors(field, errors);
        return errors.length === 0;
    }

    validateFile(fileInput) {
        const file = fileInput.files[0];
        if (!file) return true;

        const errors = [];
        const maxSize = 5 * 1024 * 1024; // 5MB
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif'];

        // Validar tamanho
        if (file.size > maxSize) {
            errors.push(`Arquivo muito grande. Máximo permitido: 5MB`);
        }

        // Validar tipo
        if (!allowedTypes.includes(file.type)) {
            errors.push(`Tipo de arquivo não permitido. Use: JPG, JPEG, PNG ou GIF`);
        }

        // Validar nome do arquivo (segurança)
        if (!/^[a-zA-Z0-9._-]+$/.test(file.name)) {
            errors.push(`Nome do arquivo contém caracteres inválidos`);
        }

        this.showFieldErrors(fileInput, errors);
        return errors.length === 0;
    }

    validateForm(form) {
        let isValid = true;
        const fields = form.querySelectorAll('input, textarea, select');

        fields.forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });

        // Validação especial: CDC obrigatório para COMPRAS
        const setorField = form.querySelector('input[name="usuario_setor"]');
        const cdcField = form.querySelector('input[name="cdc"]');
        
        if (setorField && cdcField) {
            const setorValue = setorField.value.toUpperCase();
            if ((setorValue.includes('COMPRAS') || setorValue.includes('COMPRA')) && !cdcField.value.trim()) {
                this.showFieldErrors(cdcField, ['CDC é obrigatório para o setor COMPRAS']);
                isValid = false;
            }
        }

        return isValid;
    }

    checkComprasSetor(setorValue, form) {
        const cdcField = form.querySelector('input[name="cdc"]');
        if (cdcField) {
            const isCompras = setorValue.toUpperCase().includes('COMPRAS') || 
                            setorValue.toUpperCase().includes('COMPRA');
            
            if (isCompras) {
                cdcField.setAttribute('required', 'required');
                cdcField.parentElement.classList.add('required-for-compras');
                
                // Adicionar aviso visual
                let warning = cdcField.parentElement.querySelector('.compras-warning');
                if (!warning) {
                    warning = document.createElement('div');
                    warning.className = 'alert alert-warning mt-2 compras-warning';
                    warning.innerHTML = '<i class="bi bi-exclamation-triangle"></i> CDC é obrigatório para o setor COMPRAS';
                    cdcField.parentElement.appendChild(warning);
                }
            } else {
                cdcField.removeAttribute('required');
                cdcField.parentElement.classList.remove('required-for-compras');
                
                // Remover aviso
                const warning = cdcField.parentElement.querySelector('.compras-warning');
                if (warning) warning.remove();
            }
        }
    }

    showPasswordStrength(passwordField) {
        const password = passwordField.value;
        let strengthContainer = document.getElementById('password-strength');
        
        if (!strengthContainer) {
            strengthContainer = document.createElement('div');
            strengthContainer.id = 'password-strength';
            strengthContainer.className = 'mt-2';
            passwordField.parentElement.appendChild(strengthContainer);
        }

        if (!password) {
            strengthContainer.innerHTML = '';
            return;
        }

        const strength = this.calculatePasswordStrength(password);
        const strengthClass = strength.class;
        const strengthText = strength.text;

        strengthContainer.innerHTML = `
            <div class="password-strength">
                <div class="progress" style="height: 5px;">
                    <div class="progress-bar bg-${strengthClass}" 
                         style="width: ${strength.percentage}%"></div>
                </div>
                <small class="text-${strengthClass}">${strengthText}</small>
            </div>
        `;
    }

    calculatePasswordStrength(password) {
        let score = 0;
        
        // Comprimento
        if (password.length >= 8) score += 2;
        else if (password.length >= 6) score += 1;
        
        // Minúsculas
        if (/[a-z]/.test(password)) score += 1;
        
        // Maiúsculas
        if (/[A-Z]/.test(password)) score += 1;
        
        // Números
        if (/[0-9]/.test(password)) score += 1;
        
        // Símbolos
        if (/[^A-Za-z0-9]/.test(password)) score += 1;

        if (score < 3) return { class: 'danger', text: 'Fraca', percentage: 25 };
        if (score < 5) return { class: 'warning', text: 'Média', percentage: 50 };
        if (score < 6) return { class: 'info', text: 'Boa', percentage: 75 };
        return { class: 'success', text: 'Forte', percentage: 100 };
    }

    showFieldErrors(field, errors) {
        this.clearErrors(field);

        if (errors.length === 0) {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
            return;
        }

        field.classList.add('is-invalid');
        field.classList.remove('is-valid');

        // Criar container de erros
        const errorContainer = document.createElement('div');
        errorContainer.className = 'invalid-feedback field-errors';
        errorContainer.innerHTML = errors.map(error => `<div>${error}</div>`).join('');

        field.parentElement.appendChild(errorContainer);
    }

    clearErrors(field) {
        const existingErrors = field.parentElement.querySelectorAll('.field-errors');
        existingErrors.forEach(error => error.remove());
        
        field.classList.remove('is-invalid', 'is-valid');
    }

    getFieldLabel(field) {
        const label = field.parentElement.querySelector('label');
        if (label) {
            return label.textContent.replace('*', '').trim();
        }
        
        const placeholder = field.getAttribute('placeholder');
        if (placeholder) {
            return placeholder.replace('Digite', '').replace('...', '').trim();
        }
        
        return field.name.charAt(0).toUpperCase() + field.name.slice(1);
    }

    getPatternErrorMessage(fieldName) {
        const messages = {
            username: 'Username só pode conter letras, números, _ e -',
            password: 'Senha deve conter pelo menos uma letra e um número',
            email: 'Email deve ter um formato válido (exemplo@dominio.com)',
            ramal: 'Ramal deve conter apenas números (3-6 dígitos)'
        };
        return messages[fieldName] || 'Formato inválido';
    }

    // Método público para sanitizar entrada
    static sanitizeInput(input) {
        return input.replace(/[<>\"'&]/g, function(match) {
            const map = {
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#x27;',
                '&': '&amp;'
            };
            return map[match];
        });
    }

    // Método público para validação manual
    static validate(fieldName, value) {
        const validator = new FormValidator();
        const mockField = { name: fieldName, value: value };
        return validator.validateField(mockField);
    }
}

// Inicializar validador quando o script carregar
const formValidator = new FormValidator();

// Exportar para uso global
window.FormValidator = FormValidator;