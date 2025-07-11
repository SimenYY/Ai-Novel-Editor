"""
增强型提示词模板系统 - 支持变量替换、条件逻辑和三层模式
整合现有系统，提供简化但强大的提示词工程能力
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
import re
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PromptMode(Enum):
    """提示词模式枚举 - 继承现有三层架构"""
    FAST = "fast"          # 快速模式 - 20字符内，简洁直接
    BALANCED = "balanced"  # 平衡模式 - 50-100字符，适中详细  
    FULL = "full"         # 全局模式 - 100-300字符，丰富详细


class CompletionType(Enum):
    """补全类型枚举 - 继承现有分类系统"""
    CHARACTER = "character"     # 角色描写
    LOCATION = "location"       # 场景描写
    DIALOGUE = "dialogue"       # 对话
    ACTION = "action"          # 动作描写
    EMOTION = "emotion"        # 情感描写
    PLOT = "plot"             # 情节推进
    DESCRIPTION = "description" # 环境描写
    TRANSITION = "transition"   # 转场
    TEXT = "text"             # 一般文本


@dataclass
class PromptVariable:
    """提示词变量定义"""
    name: str                          # 变量名
    description: str                   # 变量描述
    var_type: str = "string"          # 变量类型: string, int, bool, list
    default_value: Any = None         # 默认值
    required: bool = False            # 是否必填
    choices: Optional[List[str]] = None # 可选值列表


@dataclass
class PromptTemplate:
    """
    增强型提示词模板
    支持变量替换、条件逻辑、模式适配
    """
    # 基本信息
    id: str                           # 模板唯一ID
    name: str                         # 模板名称
    description: str                  # 模板描述
    category: str = "general"         # 模板分类
    
    # 模式配置
    mode_templates: Dict[PromptMode, str] = field(default_factory=dict)  # 各模式的模板内容
    completion_types: List[CompletionType] = field(default_factory=list) # 适用的补全类型
    
    # 模板内容
    system_prompt: str = ""           # 系统提示词
    user_template: str = ""           # 用户模板（通用，如果没有模式特定模板）
    
    # 变量系统
    variables: List[PromptVariable] = field(default_factory=list)        # 模板变量
    
    # AI参数
    max_tokens: Dict[PromptMode, int] = field(default_factory=dict)      # 各模式的token限制
    temperature: float = 0.7          # 温度参数
    
    # 元数据
    author: str = "system"            # 模板作者
    version: str = "1.0"             # 模板版本
    created_at: Optional[str] = None  # 创建时间
    is_builtin: bool = False         # 是否内置模板
    is_active: bool = True           # 是否启用

    def get_template_for_mode(self, mode: PromptMode) -> str:
        """获取指定模式的模板内容"""
        if mode in self.mode_templates:
            return self.mode_templates[mode]
        return self.user_template

    def get_max_tokens_for_mode(self, mode: PromptMode) -> int:
        """获取指定模式的token限制"""
        if mode in self.max_tokens:
            return self.max_tokens[mode]
        
        # 默认token配置
        default_tokens = {
            PromptMode.FAST: 50,
            PromptMode.BALANCED: 150,
            PromptMode.FULL: 400
        }
        return default_tokens.get(mode, 150)

    def supports_completion_type(self, completion_type: CompletionType) -> bool:
        """检查是否支持指定的补全类型"""
        if not self.completion_types:
            return True  # 空列表表示支持所有类型
        return completion_type in self.completion_types

    def get_variables_dict(self) -> Dict[str, PromptVariable]:
        """获取变量字典"""
        return {var.name: var for var in self.variables}


class PromptRenderer:
    """
    提示词渲染器 - 处理变量替换和条件逻辑
    使用简化的模板语法，易于理解和维护
    """
    
    def __init__(self):
        # 变量替换模式: {variable_name}
        self.variable_pattern = re.compile(r'\{([^}]+)\}')
        
        # 条件逻辑模式: {if condition}...{endif} 或 {if condition}...{else}...{endif}
        self.condition_pattern = re.compile(
            r'\{if\s+([^}]+)\}(.*?)(?:\{else\}(.*?))?\{endif\}', 
            re.DOTALL
        )
    
    def render(self, template: str, context: Dict[str, Any]) -> str:
        """
        渲染模板，支持变量替换和条件逻辑
        
        支持的语法：
        - {variable_name} - 简单变量替换
        - {if variable_name}...{endif} - 条件显示
        - {if variable_name}...{else}...{endif} - 条件分支
        """
        try:
            # 1. 处理条件逻辑
            rendered = self._process_conditions(template, context)
            
            # 2. 处理变量替换
            rendered = self._process_variables(rendered, context)
            
            return rendered.strip()
        
        except Exception as e:
            logger.error(f"提示词渲染失败: {e}")
            return template  # 出错时返回原模板
    
    def _process_conditions(self, template: str, context: Dict[str, Any]) -> str:
        """处理条件逻辑"""
        def replace_condition(match):
            condition_expr = match.group(1).strip()
            if_content = match.group(2)
            else_content = match.group(3) if match.group(3) else ""
            
            # 简单的条件判断 - 检查变量是否存在且为真值
            if self._evaluate_condition(condition_expr, context):
                return if_content
            else:
                return else_content
        
        return self.condition_pattern.sub(replace_condition, template)
    
    def _process_variables(self, template: str, context: Dict[str, Any]) -> str:
        """处理变量替换"""
        def replace_variable(match):
            var_name = match.group(1).strip()
            
            # 支持点号访问嵌套属性
            if '.' in var_name:
                value = self._get_nested_value(context, var_name)
            else:
                value = context.get(var_name, f"{{{var_name}}}")  # 未找到变量时保留原样
            
            return str(value) if value is not None else ""
        
        return self.variable_pattern.sub(replace_variable, template)
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """评估简单条件表达式"""
        # 支持简单的条件：变量名、!变量名、变量名==值
        condition = condition.strip()
        
        if condition.startswith('!'):
            # 否定条件
            var_name = condition[1:].strip()
            return not bool(context.get(var_name))
        elif '==' in condition:
            # 等值比较
            var_name, expected_value = [s.strip() for s in condition.split('==', 1)]
            actual_value = str(context.get(var_name, ''))
            expected_value = expected_value.strip('"\'')  # 去除引号
            return actual_value == expected_value
        else:
            # 简单存在性检查
            return bool(context.get(condition))
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """获取嵌套字典的值"""
        keys = key_path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value


class EnhancedPromptManager:
    """
    增强型提示词管理器
    整合现有系统，提供统一的模板管理接口
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".config" / "ai-novel-editor"
        self.templates_dir = self.config_dir / "prompt_templates"
        self.custom_templates_file = self.templates_dir / "custom_templates.json"
        
        # 确保目录存在
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # 模板存储
        self.builtin_templates: Dict[str, PromptTemplate] = {}
        self.custom_templates: Dict[str, PromptTemplate] = {}
        
        # 渲染器
        self.renderer = PromptRenderer()
        
        # 初始化
        self._load_builtin_templates()
        self._load_custom_templates()
    
    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """获取模板"""
        # 优先使用自定义模板
        if template_id in self.custom_templates:
            return self.custom_templates[template_id]
        return self.builtin_templates.get(template_id)
    
    def get_templates_for_type(self, completion_type: CompletionType, 
                              mode: Optional[PromptMode] = None) -> List[PromptTemplate]:
        """获取支持指定类型的模板列表"""
        templates = []
        
        # 合并内置和自定义模板
        all_templates = {**self.builtin_templates, **self.custom_templates}
        
        for template in all_templates.values():
            if not template.is_active:
                continue
                
            if template.supports_completion_type(completion_type):
                # 检查是否有对应模式的模板
                if mode is None or template.get_template_for_mode(mode):
                    templates.append(template)
        
        # 按优先级排序：自定义模板优先，然后按名称排序
        templates.sort(key=lambda t: (t.is_builtin, t.name))
        return templates
    
    def render_template(self, template_id: str, mode: PromptMode, 
                       context: Dict[str, Any]) -> Optional[str]:
        """渲染指定模板"""
        template = self.get_template(template_id)
        if not template:
            logger.warning(f"模板不存在: {template_id}")
            return None
        
        try:
            # 获取模式对应的模板内容
            template_content = template.get_template_for_mode(mode)
            if not template_content:
                logger.warning(f"模板 {template_id} 不支持模式 {mode}")
                return None
            
            # 添加系统提示词到上下文
            if template.system_prompt:
                context['system_prompt'] = template.system_prompt
            
            # 渲染模板
            rendered = self.renderer.render(template_content, context)
            return rendered
            
        except Exception as e:
            logger.error(f"渲染模板失败 {template_id}: {e}")
            return None
    
    def save_custom_template(self, template: PromptTemplate) -> bool:
        """保存自定义模板"""
        try:
            # 标记为非内置模板
            template.is_builtin = False
            
            # 添加到自定义模板集合
            self.custom_templates[template.id] = template
            
            # 持久化到文件
            self._save_custom_templates()
            
            logger.info(f"保存自定义模板成功: {template.id}")
            return True
            
        except Exception as e:
            logger.error(f"保存自定义模板失败: {e}")
            return False
    
    def delete_custom_template(self, template_id: str) -> bool:
        """删除自定义模板"""
        if template_id in self.custom_templates:
            del self.custom_templates[template_id]
            self._save_custom_templates()
            logger.info(f"删除自定义模板成功: {template_id}")
            return True
        return False
    
    def get_template_categories(self) -> List[str]:
        """获取所有模板分类"""
        categories = set()
        all_templates = {**self.builtin_templates, **self.custom_templates}
        
        for template in all_templates.values():
            if template.is_active:
                categories.add(template.category)
        
        return sorted(list(categories))
    
    def _load_builtin_templates(self):
        """加载内置模板 - 稍后实现具体模板"""
        pass
    
    def _load_custom_templates(self):
        """加载自定义模板"""
        try:
            if self.custom_templates_file.exists():
                with open(self.custom_templates_file, 'r', encoding='utf-8') as f:
                    templates_data = json.load(f)
                
                for template_data in templates_data:
                    try:
                        template = self._dict_to_template(template_data)
                        self.custom_templates[template.id] = template
                    except Exception as e:
                        logger.error(f"加载自定义模板失败: {e}")
                        
        except Exception as e:
            logger.error(f"加载自定义模板文件失败: {e}")
    
    def _save_custom_templates(self):
        """保存自定义模板到文件"""
        try:
            templates_data = []
            for template in self.custom_templates.values():
                templates_data.append(self._template_to_dict(template))
            
            with open(self.custom_templates_file, 'w', encoding='utf-8') as f:
                json.dump(templates_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存自定义模板文件失败: {e}")
    
    def _template_to_dict(self, template: PromptTemplate) -> Dict[str, Any]:
        """模板对象转字典"""
        return {
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'category': template.category,
            'mode_templates': {mode.value: content for mode, content in template.mode_templates.items()},
            'completion_types': [ct.value for ct in template.completion_types],
            'system_prompt': template.system_prompt,
            'user_template': template.user_template,
            'variables': [
                {
                    'name': var.name,
                    'description': var.description,
                    'var_type': var.var_type,
                    'default_value': var.default_value,
                    'required': var.required,
                    'choices': var.choices
                }
                for var in template.variables
            ],
            'max_tokens': {mode.value: tokens for mode, tokens in template.max_tokens.items()},
            'temperature': template.temperature,
            'author': template.author,
            'version': template.version,
            'created_at': template.created_at,
            'is_active': template.is_active
        }
    
    def _dict_to_template(self, data: Dict[str, Any]) -> PromptTemplate:
        """字典转模板对象"""
        # 转换mode_templates
        mode_templates = {}
        for mode_str, content in data.get('mode_templates', {}).items():
            try:
                mode = PromptMode(mode_str)
                mode_templates[mode] = content
            except ValueError:
                logger.warning(f"未知的提示词模式: {mode_str}")
        
        # 转换completion_types
        completion_types = []
        for ct_str in data.get('completion_types', []):
            try:
                completion_types.append(CompletionType(ct_str))
            except ValueError:
                logger.warning(f"未知的补全类型: {ct_str}")
        
        # 转换variables
        variables = []
        for var_data in data.get('variables', []):
            variables.append(PromptVariable(
                name=var_data['name'],
                description=var_data['description'],
                var_type=var_data.get('var_type', 'string'),
                default_value=var_data.get('default_value'),
                required=var_data.get('required', False),
                choices=var_data.get('choices')
            ))
        
        # 转换max_tokens
        max_tokens = {}
        for mode_str, tokens in data.get('max_tokens', {}).items():
            try:
                mode = PromptMode(mode_str)
                max_tokens[mode] = tokens
            except ValueError:
                logger.warning(f"未知的提示词模式: {mode_str}")
        
        return PromptTemplate(
            id=data['id'],
            name=data['name'],
            description=data['description'],
            category=data.get('category', 'general'),
            mode_templates=mode_templates,
            completion_types=completion_types,
            system_prompt=data.get('system_prompt', ''),
            user_template=data.get('user_template', ''),
            variables=variables,
            max_tokens=max_tokens,
            temperature=data.get('temperature', 0.7),
            author=data.get('author', 'user'),
            version=data.get('version', '1.0'),
            created_at=data.get('created_at'),
            is_builtin=False,
            is_active=data.get('is_active', True)
        )


# 导出主要类
__all__ = [
    'PromptMode', 'CompletionType', 'PromptVariable', 'PromptTemplate',
    'PromptRenderer', 'EnhancedPromptManager'
]