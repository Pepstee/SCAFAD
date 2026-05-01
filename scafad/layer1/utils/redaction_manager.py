#!/usr/bin/env python3
"""
SCAFAD Layer 1: Redaction Manager Utility
========================================

The Redaction Manager handles PII redaction policies and data redaction operations
for Layer 1's behavioral intake zone. It provides:

- PII field identification and redaction
- Configurable redaction policies
- Multiple redaction strategies
- Redaction audit logging
- Performance-optimized redaction
- Redaction quality validation

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import json
import logging
import hashlib
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from enum import Enum, auto
from datetime import datetime, timezone
import copy
from collections import defaultdict

# =============================================================================
# Redaction Manager Data Models
# =============================================================================

class RedactionStrategy(Enum):
    """Redaction strategies"""
    MASK = "mask"                   # Replace with asterisks
    HASH = "hash"                   # Replace with hash
    ENCRYPT = "encrypt"             # Replace with encrypted value
    REMOVE = "remove"               # Remove field entirely
    ANONYMIZE = "anonymize"         # Replace with anonymized value
    PSEUDONYMIZE = "pseudonymize"   # Replace with pseudonymized value

class RedactionLevel(Enum):
    """Redaction levels"""
    NONE = "none"                   # No redaction
    PARTIAL = "partial"             # Partial redaction
    FULL = "full"                   # Complete redaction
    SELECTIVE = "selective"         # Selective redaction based on rules

class PIIFieldType(Enum):
    """PII field types"""
    EMAIL = "email"                 # Email addresses
    PHONE = "phone"                 # Phone numbers
    SSN = "ssn"                     # Social Security Numbers
    CREDIT_CARD = "credit_card"     # Credit card numbers
    IP_ADDRESS = "ip_address"       # IP addresses
    USER_ID = "user_id"             # User identifiers
    NAME = "name"                   # Personal names
    ADDRESS = "address"             # Physical addresses
    DATE_OF_BIRTH = "date_of_birth" # Date of birth
    CUSTOM = "custom"               # Custom PII fields

@dataclass
class RedactionPolicy:
    """Redaction policy definition"""
    policy_id: str
    name: str
    description: str
    field_rules: Dict[str, Dict[str, Any]]
    default_strategy: RedactionStrategy
    default_level: RedactionLevel
    preserve_structure: bool = True
    audit_redactions: bool = True
    performance_mode: bool = False
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class RedactionRule:
    """Individual redaction rule"""
    field_pattern: str
    field_type: PIIFieldType
    strategy: RedactionStrategy
    level: RedactionLevel
    priority: int
    conditions: Dict[str, Any]
    exceptions: List[str]
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class RedactionResult:
    """Result of redaction operation"""
    original_data: Any
    redacted_data: Any
    redaction_applied: Dict[str, Dict[str, Any]]
    fields_redacted: List[str]
    fields_preserved: List[str]
    redaction_time_ms: float
    policy_used: str
    audit_trail: List[str]
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class RedactionAudit:
    """Redaction audit record"""
    timestamp: datetime
    policy_id: str
    field_name: str
    field_type: PIIFieldType
    strategy: RedactionStrategy
    level: RedactionLevel
    original_value: str
    redacted_value: str
    redaction_reason: str
    performance_metrics: Dict[str, float]
    metadata: Optional[Dict[str, Any]] = None

# =============================================================================
# Redaction Manager Core Class
# =============================================================================

class RedactionManager:
    """
    Redaction Manager for PII data handling
    
    The Redaction Manager provides comprehensive PII redaction capabilities
    with configurable policies and multiple redaction strategies.
    """
    
    def __init__(self, config: Any = None):
        """Initialize the Redaction Manager"""
        self.config = config
        self.logger = logging.getLogger("SCAFAD.Layer1.RedactionManager")
        
        # Redaction policies
        self.policies: Dict[str, RedactionPolicy] = {}
        self.active_policy: Optional[str] = None
        
        # Redaction rules
        self.redaction_rules: List[RedactionRule] = []
        
        # PII detection patterns
        self.pii_patterns: Dict[PIIFieldType, List[re.Pattern]] = {}
        
        # Performance tracking
        self.manager_stats = {
            'total_redactions': 0,
            'total_fields_redacted': 0,
            'average_redaction_time_ms': 0.0,
            'total_bytes_processed': 0
        }
        
        # Audit trail
        self.audit_trail: List[RedactionAudit] = []
        
        # Initialize default patterns and policies
        self._initialize_pii_patterns()
        self._initialize_default_policies()
        
        self.logger.info("Redaction Manager initialized")
    
    def register_policy(self, policy: RedactionPolicy) -> bool:
        """
        Register a redaction policy
        
        Args:
            policy: RedactionPolicy to register
            
        Returns:
            bool: True if registration successful
        """
        try:
            # Validate policy
            if not self._validate_policy(policy):
                self.logger.error(f"Policy validation failed for {policy.policy_id}")
                return False
            
            # Register policy
            self.policies[policy.policy_id] = policy
            
            # Set as active if first policy
            if not self.active_policy:
                self.active_policy = policy.policy_id
            
            self.logger.info(f"Redaction policy {policy.policy_id} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register policy {policy.policy_id}: {str(e)}")
            return False
    
    def set_active_policy(self, policy_id: str) -> bool:
        """
        Set active redaction policy
        
        Args:
            policy_id: Policy ID to activate
            
        Returns:
            bool: True if activation successful
        """
        if policy_id not in self.policies:
            self.logger.error(f"Policy {policy_id} not found")
            return False
        
        self.active_policy = policy_id
        self.logger.info(f"Active policy set to {policy_id}")
        return True
    
    def add_redaction_rule(self, rule: RedactionRule):
        """
        Add a redaction rule
        
        Args:
            rule: RedactionRule to add
        """
        try:
            # Validate rule
            if not self._validate_rule(rule):
                self.logger.error(f"Rule validation failed for {rule.field_pattern}")
                return
            
            # Add rule
            self.redaction_rules.append(rule)
            
            # Sort by priority (higher priority first)
            self.redaction_rules.sort(key=lambda r: r.priority, reverse=True)
            
            self.logger.info(f"Redaction rule added for {rule.field_pattern}")
            
        except Exception as e:
            self.logger.error(f"Failed to add redaction rule: {str(e)}")
    
    def redact_data(self, data: Any, policy_id: Optional[str] = None,
                    preserve_structure: Optional[bool] = None) -> RedactionResult:
        """
        Redact PII data according to policy
        
        Args:
            data: Data to redact
            policy_id: Policy ID to use (uses active policy if None)
            preserve_structure: Whether to preserve data structure
            
        Returns:
            RedactionResult with redaction details
        """
        import time
        start_time = time.time()
        
        try:
            # Get policy
            if policy_id is None:
                policy_id = self.active_policy
            
            if not policy_id or policy_id not in self.policies:
                raise ValueError(f"No valid policy specified: {policy_id}")
            
            policy = self.policies[policy_id]
            
            # Determine preserve structure setting
            if preserve_structure is None:
                preserve_structure = policy.preserve_structure
            
            # Create redaction result
            result = RedactionResult(
                original_data=copy.deepcopy(data),
                redacted_data=None,
                redaction_applied={},
                fields_redacted=[],
                fields_preserved=[],
                redaction_time_ms=0.0,
                policy_used=policy_id,
                audit_trail=[],
                metadata={}
            )
            
            # Perform redaction
            if isinstance(data, dict):
                result.redacted_data = self._redact_dict(data, policy, result, preserve_structure)
            elif isinstance(data, list):
                result.redacted_data = self._redact_list(data, policy, result, preserve_structure)
            else:
                result.redacted_data = self._redact_value(data, policy, result, preserve_structure)
            
            # Calculate redaction time
            redaction_time = (time.time() - start_time) * 1000
            result.redaction_time_ms = redaction_time
            
            # Update statistics
            self._update_manager_stats(result, redaction_time)
            
            # Generate audit trail
            if policy.audit_redactions:
                self._generate_audit_trail(result, policy)
            
            self.logger.debug(f"Data redaction completed in {redaction_time:.2f}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"Data redaction failed: {str(e)}")
            raise
    
    def get_redaction_policies(self) -> List[str]:
        """Get list of registered policy IDs"""
        return list(self.policies.keys())
    
    def get_active_policy(self) -> Optional[RedactionPolicy]:
        """Get currently active policy"""
        if self.active_policy:
            return self.policies.get(self.active_policy)
        return None
    
    def get_redaction_rules(self) -> List[RedactionRule]:
        """Get list of redaction rules"""
        return self.redaction_rules.copy()
    
    def get_audit_trail(self, filters: Optional[Dict[str, Any]] = None,
                        limit: Optional[int] = None) -> List[RedactionAudit]:
        """
        Get redaction audit trail
        
        Args:
            filters: Optional filters for audit records
            limit: Maximum number of records to return
            
        Returns:
            List of filtered audit records
        """
        try:
            filtered_audits = self.audit_trail.copy()
            
            # Apply filters
            if filters:
                filtered_audits = self._apply_audit_filters(filtered_audits, filters)
            
            # Sort by timestamp (newest first)
            filtered_audits.sort(key=lambda x: x.timestamp, reverse=True)
            
            # Apply limit
            if limit:
                filtered_audits = filtered_audits[:limit]
            
            return filtered_audits
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve audit trail: {str(e)}")
            return []
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return self.manager_stats.copy()
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _initialize_pii_patterns(self):
        """Initialize PII detection patterns"""
        # Email patterns
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.pii_patterns[PIIFieldType.EMAIL] = [email_pattern]
        
        # Phone number patterns
        phone_pattern = re.compile(r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
        self.pii_patterns[PIIFieldType.PHONE] = [phone_pattern]
        
        # SSN patterns
        ssn_pattern = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
        self.pii_patterns[PIIFieldType.SSN] = [ssn_pattern]
        
        # Credit card patterns
        cc_pattern = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
        self.pii_patterns[PIIFieldType.CREDIT_CARD] = [cc_pattern]
        
        # IP address patterns
        ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
        self.pii_patterns[PIIFieldType.IP_ADDRESS] = [ip_pattern]
        
        # User ID patterns (common formats)
        user_id_pattern = re.compile(r'\b(?:user|usr|id|uid)[-_]?\d+\b', re.IGNORECASE)
        self.pii_patterns[PIIFieldType.USER_ID] = [user_id_pattern]
    
    def _initialize_default_policies(self):
        """Initialize default redaction policies"""
        # Default privacy-focused policy
        default_policy = RedactionPolicy(
            policy_id="default_privacy",
            name="Default Privacy Policy",
            description="Default privacy-focused redaction policy",
            field_rules={
                'email': {
                    'strategy': RedactionStrategy.MASK,
                    'level': RedactionLevel.PARTIAL,
                    'preserve_domain': True
                },
                'phone': {
                    'strategy': RedactionStrategy.MASK,
                    'level': RedactionLevel.PARTIAL,
                    'preserve_country_code': True
                },
                'ssn': {
                    'strategy': RedactionStrategy.MASK,
                    'level': RedactionLevel.FULL
                },
                'credit_card': {
                    'strategy': RedactionStrategy.MASK,
                    'level': RedactionLevel.FULL
                },
                'ip_address': {
                    'strategy': RedactionStrategy.HASH,
                    'level': RedactionLevel.FULL
                },
                'user_id': {
                    'strategy': RedactionStrategy.HASH,
                    'level': RedactionLevel.FULL
                }
            },
            default_strategy=RedactionStrategy.MASK,
            default_level=RedactionLevel.PARTIAL,
            preserve_structure=True,
            audit_redactions=True,
            performance_mode=False
        )
        
        # High-performance policy
        performance_policy = RedactionPolicy(
            policy_id="high_performance",
            name="High Performance Policy",
            description="High-performance redaction policy with minimal overhead",
            field_rules={
                'email': {
                    'strategy': RedactionStrategy.MASK,
                    'level': RedactionLevel.PARTIAL
                },
                'phone': {
                    'strategy': RedactionStrategy.MASK,
                    'level': RedactionLevel.PARTIAL
                },
                'ssn': {
                    'strategy': RedactionStrategy.MASK,
                    'level': RedactionLevel.FULL
                },
                'credit_card': {
                    'strategy': RedactionStrategy.MASK,
                    'level': RedactionLevel.FULL
                }
            },
            default_strategy=RedactionStrategy.MASK,
            default_level=RedactionLevel.PARTIAL,
            preserve_structure=True,
            audit_redactions=False,
            performance_mode=True
        )
        
        # Register policies
        self.register_policy(default_policy)
        self.register_policy(performance_policy)
    
    def _validate_policy(self, policy: RedactionPolicy) -> bool:
        """Validate redaction policy"""
        try:
            if not policy.policy_id:
                return False
            
            if not policy.name:
                return False
            
            if not policy.field_rules:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_rule(self, rule: RedactionRule) -> bool:
        """Validate redaction rule"""
        try:
            if not rule.field_pattern:
                return False
            
            if not rule.field_type:
                return False
            
            if not rule.strategy:
                return False
            
            if not rule.level:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _redact_dict(self, data: Dict[str, Any], policy: RedactionPolicy,
                     result: RedactionResult, preserve_structure: bool) -> Dict[str, Any]:
        """Redact dictionary data"""
        redacted_data = {}
        
        for key, value in data.items():
            # Check if field should be redacted
            redaction_info = self._should_redact_field(key, value, policy)
            
            if redaction_info:
                # Apply redaction
                redacted_value = self._apply_redaction(value, redaction_info, policy)
                redacted_data[key] = redacted_value
                
                # Update result
                result.fields_redacted.append(key)
                result.redaction_applied[key] = redaction_info
                
                # Add to audit trail
                result.audit_trail.append(
                    f"Field '{key}' redacted using {redaction_info['strategy'].value} strategy"
                )
            else:
                # Preserve field
                if isinstance(value, (dict, list)):
                    redacted_data[key] = self._redact_nested_data(value, policy, result, preserve_structure)
                else:
                    redacted_data[key] = value
                
                result.fields_preserved.append(key)
        
        return redacted_data
    
    def _redact_list(self, data: List[Any], policy: RedactionPolicy,
                     result: RedactionResult, preserve_structure: bool) -> List[Any]:
        """Redact list data"""
        redacted_data = []
        
        for i, item in enumerate(data):
            if isinstance(item, (dict, list)):
                redacted_item = self._redact_nested_data(item, policy, result, preserve_structure)
            else:
                redacted_item = item
            
            redacted_data.append(redacted_item)
        
        return redacted_data
    
    def _redact_nested_data(self, data: Any, policy: RedactionPolicy,
                           result: RedactionResult, preserve_structure: bool) -> Any:
        """Redact nested data structures"""
        if isinstance(data, dict):
            return self._redact_dict(data, policy, result, preserve_structure)
        elif isinstance(data, list):
            return self._redact_list(data, policy, result, preserve_structure)
        else:
            return data
    
    def _redact_value(self, data: Any, policy: RedactionPolicy,
                     result: RedactionResult, preserve_structure: bool) -> Any:
        """Redact single value"""
        # For single values, check if they match any PII patterns
        if isinstance(data, str):
            for field_type, patterns in self.pii_patterns.items():
                for pattern in patterns:
                    if pattern.search(data):
                        # Create redaction info
                        redaction_info = {
                            'field_type': field_type,
                            'strategy': policy.default_strategy,
                            'level': policy.default_level,
                            'pattern_matched': pattern.pattern
                        }
                        
                        # Apply redaction
                        redacted_value = self._apply_redaction(data, redaction_info, policy)
                        
                        # Update result
                        result.fields_redacted.append(f"value_{field_type.value}")
                        result.redaction_applied[f"value_{field_type.value}"] = redaction_info
                        
                        return redacted_value
        
        return data
    
    def _should_redact_field(self, field_name: str, field_value: Any, 
                            policy: RedactionPolicy) -> Optional[Dict[str, Any]]:
        """Determine if a field should be redacted"""
        # Check policy field rules first
        for rule_pattern, rule_config in policy.field_rules.items():
            if self._field_matches_pattern(field_name, rule_pattern):
                return {
                    'field_type': self._infer_field_type(field_name, field_value),
                    'strategy': rule_config.get('strategy', policy.default_strategy),
                    'level': rule_config.get('level', policy.default_level),
                    'rule_pattern': rule_pattern,
                    'rule_config': rule_config
                }
        
        # Check redaction rules
        for rule in self.redaction_rules:
            if self._field_matches_pattern(field_name, rule.field_pattern):
                # Check conditions
                if self._rule_conditions_met(rule, field_name, field_value):
                    return {
                        'field_type': rule.field_type,
                        'strategy': rule.strategy,
                        'level': rule.level,
                        'rule': rule
                    }
        
        # Check PII patterns in field value
        if isinstance(field_value, str):
            for field_type, patterns in self.pii_patterns.items():
                for pattern in patterns:
                    if pattern.search(field_value):
                        return {
                            'field_type': field_type,
                            'strategy': policy.default_strategy,
                            'level': policy.default_level,
                            'pattern_matched': pattern.pattern
                        }
        
        return None
    
    def _field_matches_pattern(self, field_name: str, pattern: str) -> bool:
        """Check if field name matches pattern"""
        try:
            return re.search(pattern, field_name, re.IGNORECASE) is not None
        except re.error:
            # If pattern is invalid, treat as exact match
            return field_name.lower() == pattern.lower()
    
    def _infer_field_type(self, field_name: str, field_value: Any) -> PIIFieldType:
        """Infer PII field type from field name and value"""
        field_name_lower = field_name.lower()
        
        # Check field name patterns
        if any(keyword in field_name_lower for keyword in ['email', 'mail']):
            return PIIFieldType.EMAIL
        elif any(keyword in field_name_lower for keyword in ['phone', 'tel', 'mobile']):
            return PIIFieldType.PHONE
        elif any(keyword in field_name_lower for keyword in ['ssn', 'social']):
            return PIIFieldType.SSN
        elif any(keyword in field_name_lower for keyword in ['credit', 'card', 'cc']):
            return PIIFieldType.CREDIT_CARD
        elif any(keyword in field_name_lower for keyword in ['ip', 'address']):
            return PIIFieldType.IP_ADDRESS
        elif any(keyword in field_name_lower for keyword in ['user', 'uid', 'id']):
            return PIIFieldType.USER_ID
        elif any(keyword in field_name_lower for keyword in ['name', 'first', 'last']):
            return PIIFieldType.NAME
        elif any(keyword in field_name_lower for keyword in ['address', 'street', 'city']):
            return PIIFieldType.ADDRESS
        elif any(keyword in field_name_lower for keyword in ['birth', 'dob', 'age']):
            return PIIFieldType.DATE_OF_BIRTH
        
        # Check value patterns
        if isinstance(field_value, str):
            for field_type, patterns in self.pii_patterns.items():
                for pattern in patterns:
                    if pattern.search(field_value):
                        return field_type
        
        return PIIFieldType.CUSTOM
    
    def _rule_conditions_met(self, rule: RedactionRule, field_name: str, 
                            field_value: Any) -> bool:
        """Check if redaction rule conditions are met"""
        # Check exceptions
        for exception in rule.exceptions:
            if self._field_matches_pattern(field_name, exception):
                return False
        
        # Check conditions (placeholder for future enhancement)
        # For now, all conditions are considered met
        return True
    
    def _apply_redaction(self, value: Any, redaction_info: Dict[str, Any],
                         policy: RedactionPolicy) -> Any:
        """Apply redaction to a value"""
        strategy = redaction_info.get('strategy', policy.default_strategy)
        level = redaction_info.get('level', policy.default_level)
        
        if not isinstance(value, str):
            value = str(value)
        
        if strategy == RedactionStrategy.MASK:
            return self._apply_mask_redaction(value, level, redaction_info)
        elif strategy == RedactionStrategy.HASH:
            return self._apply_hash_redaction(value, level)
        elif strategy == RedactionStrategy.ENCRYPT:
            return self._apply_encrypt_redaction(value, level)
        elif strategy == RedactionStrategy.REMOVE:
            return None
        elif strategy == RedactionStrategy.ANONYMIZE:
            return self._apply_anonymize_redaction(value, level)
        elif strategy == RedactionStrategy.PSEUDONYMIZE:
            return self._apply_pseudonymize_redaction(value, level)
        else:
            return value
    
    def _apply_mask_redaction(self, value: str, level: RedactionLevel,
                             redaction_info: Dict[str, Any]) -> str:
        """Apply mask redaction"""
        if level == RedactionLevel.FULL:
            return '*' * len(value)
        elif level == RedactionLevel.PARTIAL:
            # Check for special handling based on field type
            field_type = redaction_info.get('field_type')
            
            if field_type == PIIFieldType.EMAIL:
                return self._mask_email(value, redaction_info)
            elif field_type == PIIFieldType.PHONE:
                return self._mask_phone(value, redaction_info)
            else:
                # Default partial masking
                if len(value) <= 2:
                    return '*' * len(value)
                else:
                    return value[:2] + '*' * (len(value) - 2)
        else:
            return value
    
    def _mask_email(self, email: str, redaction_info: Dict[str, Any]) -> str:
        """Mask email address"""
        if '@' not in email:
            return '*' * len(email)
        
        username, domain = email.split('@', 1)
        
        # Check if we should preserve domain
        rule_config = redaction_info.get('rule_config', {})
        preserve_domain = rule_config.get('preserve_domain', True)
        
        if preserve_domain:
            if len(username) <= 2:
                masked_username = '*' * len(username)
            else:
                masked_username = username[:2] + '*' * (len(username) - 2)
            return f"{masked_username}@{domain}"
        else:
            return f"{'*' * len(username)}@{'*' * len(domain)}"
    
    def _mask_phone(self, phone: str, redaction_info: Dict[str, Any]) -> str:
        """Mask phone number"""
        # Remove non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Check if we should preserve country code
        rule_config = redaction_info.get('rule_config', {})
        preserve_country_code = rule_config.get('preserve_country_code', True)
        
        if preserve_country_code and len(digits) > 10:
            # Assume first digits are country code
            country_code = digits[:len(digits) - 10]
            local_number = digits[len(digits) - 10:]
            masked_local = local_number[:3] + '*' * (len(local_number) - 3)
            return f"+{country_code}-{masked_local}"
        else:
            # Mask all but last 4 digits
            if len(digits) <= 4:
                return '*' * len(digits)
            else:
                return '*' * (len(digits) - 4) + digits[-4:]
    
    def _apply_hash_redaction(self, value: str, level: RedactionLevel) -> str:
        """Apply hash redaction"""
        if level == RedactionLevel.FULL:
            return hashlib.sha256(value.encode()).hexdigest()[:16]
        else:
            # Partial hash - hash only sensitive parts
            return value[:2] + hashlib.md5(value[2:].encode()).hexdigest()[:8]
    
    def _apply_encrypt_redaction(self, value: str, level: RedactionLevel) -> str:
        """Apply encryption redaction (placeholder)"""
        # In a real implementation, this would use proper encryption
        return f"[ENCRYPTED_{level.value.upper()}]"
    
    def _apply_anonymize_redaction(self, value: str, level: RedactionLevel) -> str:
        """Apply anonymization redaction"""
        if level == RedactionLevel.FULL:
            return f"ANON_{hashlib.md5(value.encode()).hexdigest()[:8]}"
        else:
            return f"ANON_{value[:2]}_{hashlib.md5(value[2:].encode()).hexdigest()[:4]}"
    
    def _apply_pseudonymize_redaction(self, value: str, level: RedactionLevel) -> str:
        """Apply pseudonymization redaction"""
        if level == RedactionLevel.FULL:
            return f"PSEUDO_{hashlib.sha1(value.encode()).hexdigest()[:12]}"
        else:
            return f"PSEUDO_{value[:2]}_{hashlib.sha1(value[2:].encode()).hexdigest()[:6]}"
    
    def _update_manager_stats(self, result: RedactionResult, redaction_time: float):
        """Update manager statistics"""
        self.manager_stats['total_redactions'] += 1
        self.manager_stats['total_fields_redacted'] += len(result.fields_redacted)
        
        # Update average redaction time
        current_avg = self.manager_stats['average_redaction_time_ms']
        total_redactions = self.manager_stats['total_redactions']
        
        if total_redactions > 0:
            self.manager_stats['average_redaction_time_ms'] = (
                (current_avg * (total_redactions - 1) + redaction_time) / total_redactions
            )
        
        # Update bytes processed
        original_size = len(json.dumps(result.original_data, default=str))
        self.manager_stats['total_bytes_processed'] += original_size
    
    def _generate_audit_trail(self, result: RedactionResult, policy: RedactionPolicy):
        """Generate audit trail for redaction operations"""
        for field_name, redaction_info in result.redaction_applied.items():
            audit_record = RedactionAudit(
                timestamp=datetime.now(timezone.utc),
                policy_id=result.policy_used,
                field_name=field_name,
                field_type=redaction_info.get('field_type', PIIFieldType.CUSTOM),
                strategy=redaction_info.get('strategy', policy.default_strategy),
                level=redaction_info.get('level', policy.default_level),
                original_value=str(result.original_data.get(field_name, '')),
                redacted_value=str(result.redacted_data.get(field_name, '')),
                redaction_reason=f"Policy {result.policy_used} applied",
                performance_metrics={
                    'redaction_time_ms': result.redaction_time_ms,
                    'fields_redacted': len(result.fields_redacted)
                },
                metadata={
                    'rule_pattern': redaction_info.get('rule_pattern'),
                    'pattern_matched': redaction_info.get('pattern_matched')
                }
            )
            
            self.audit_trail.append(audit_record)
    
    def _apply_audit_filters(self, audits: List[RedactionAudit], 
                            filters: Dict[str, Any]) -> List[RedactionAudit]:
        """Apply filters to audit records"""
        filtered_audits = audits.copy()
        
        for filter_key, filter_value in filters.items():
            if filter_key == 'policy_id' and filter_value:
                filtered_audits = [a for a in filtered_audits if a.policy_id == filter_value]
            elif filter_key == 'field_type' and filter_value:
                filtered_audits = [a for a in filtered_audits if a.field_type == filter_value]
            elif filter_key == 'strategy' and filter_value:
                filtered_audits = [a for a in filtered_audits if a.strategy == filter_value]
            elif filter_key == 'level' and filter_value:
                filtered_audits = [a for a in filtered_audits if a.level == filter_value]
            elif filter_key == 'start_time' and filter_value:
                filtered_audits = [a for a in filtered_audits if a.timestamp >= filter_value]
            elif filter_key == 'end_time' and filter_value:
                filtered_audits = [a for a in filtered_audits if a.timestamp <= filter_value]
        
        return filtered_audits

# =============================================================================
# Redaction Manager Factory Functions
# =============================================================================

def create_redaction_manager(config: Optional[Any] = None) -> RedactionManager:
    """Create a redaction manager with default configuration"""
    return RedactionManager(config)

if __name__ == "__main__":
    # Example usage
    manager = create_redaction_manager()
    
    # Test data
    test_data = {
        'user_email': 'john.doe@example.com',
        'phone_number': '+1-555-123-4567',
        'ssn': '123-45-6789',
        'credit_card': '4111-1111-1111-1111',
        'ip_address': '192.168.1.100',
        'user_id': 'user_12345',
        'safe_field': 'This field should not be redacted'
    }
    
    # Redact data
    result = manager.redact_data(test_data)
    print(f"Redaction completed in {result.redaction_time_ms:.2f}ms")
    print(f"Fields redacted: {result.fields_redacted}")
    print(f"Fields preserved: {result.fields_preserved}")
    
    # Show some redacted values
    print("\nRedacted data sample:")
    for field in result.fields_redacted[:3]:
        original = result.original_data.get(field, '')
        redacted = result.redacted_data.get(field, '')
        print(f"{field}: {original} -> {redacted}")
    
    # Get audit trail
    audits = manager.get_audit_trail(limit=5)
    print(f"\nAudit trail: {len(audits)} records")
    
    # Get manager stats
    stats = manager.get_manager_stats()
    print(f"\nManager stats: {stats}")

# Backward-compat alias
RedactionPolicyManager = RedactionManager
