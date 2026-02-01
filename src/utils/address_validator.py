"""
Address validation and normalization utility for Irish addresses
Handles full addresses, postcodes, and eircodes
"""
import re
import sqlite3
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class AddressMatch:
    """Represents a matched address with confidence score"""
    full_address: str
    eircode: Optional[str]
    county: Optional[str]
    confidence: float
    source: str  # 'full', 'eircode', 'postcode'


class AddressValidator:
    """Validates and enriches Irish addresses"""
    
    # Irish county patterns for validation
    IRISH_COUNTIES = [
        'Antrim', 'Armagh', 'Carlow', 'Cavan', 'Clare', 'Cork', 'Derry', 'Donegal',
        'Down', 'Dublin', 'Fermanagh', 'Galway', 'Kerry', 'Kildare', 'Kilkenny',
        'Laois', 'Leitrim', 'Limerick', 'Longford', 'Louth', 'Mayo', 'Meath',
        'Monaghan', 'Offaly', 'Roscommon', 'Sligo', 'Tipperary', 'Tyrone',
        'Waterford', 'Westmeath', 'Wexford', 'Wicklow'
    ]
    
    # Eircode pattern: Letter-Number-Number space Letter-Number-Number-Number
    EIRCODE_PATTERN = re.compile(r'^[A-Z]\d{2}\s?[A-Z0-9]{4}$', re.IGNORECASE)
    
    # Common Irish postcode patterns (legacy system)
    POSTCODE_PATTERNS = [
        re.compile(r'^\d{1,2}$'),  # Dublin postal districts (1-24)
        re.compile(r'^[A-Z]{2,}\s?\d{1,2}[A-Z]?$', re.IGNORECASE),  # General format
    ]
    
    def __init__(self):
        """Initialize with address database if available"""
        self.address_cache = {}
        
    def validate_eircode(self, eircode: str) -> bool:
        """Validate eircode format"""
        if not eircode:
            return False
        return bool(self.EIRCODE_PATTERN.match(eircode.strip()))
    
    def normalize_eircode(self, eircode: str) -> Optional[str]:
        """Normalize eircode to standard format (XXX XXXX)"""
        if not eircode:
            return None
        
        # Remove all spaces and convert to uppercase
        clean = re.sub(r'\s+', '', eircode.upper())
        
        # Check if it matches eircode pattern (7 characters)
        if len(clean) == 7 and re.match(r'^[A-Z]\d{2}[A-Z0-9]{4}$', clean):
            # Format as XXX XXXX
            return f"{clean[:3]} {clean[3:]}"
        
        return None
    
    def is_postcode(self, address_input: str) -> bool:
        """Check if input appears to be just a postcode"""
        cleaned = address_input.strip()
        
        # Check for eircode
        if self.validate_eircode(cleaned):
            return True
        
        # Check for legacy postcode patterns
        for pattern in self.POSTCODE_PATTERNS:
            if pattern.match(cleaned):
                return True
        
        return False
    
    def extract_eircode(self, address_text: str) -> Optional[str]:
        """Extract eircode from address text"""
        # Look for eircode pattern in the text
        words = address_text.split()
        for i, word in enumerate(words):
            # Check single word
            if self.validate_eircode(word):
                return self.normalize_eircode(word)
            
            # Check two consecutive words (for spaced eircodes)
            if i < len(words) - 1:
                combined = word + words[i + 1]
                if self.validate_eircode(combined):
                    return self.normalize_eircode(combined)
        
        return None
    
    def extract_county(self, address_text: str) -> Optional[str]:
        """Extract county from address text"""
        address_lower = address_text.lower()
        for county in self.IRISH_COUNTIES:
            if county.lower() in address_lower:
                return county
        return None
    
    def parse_address_input(self, user_input: str) -> Dict:
        """
        Parse user address input and determine what type of address info we have
        
        Returns:
            dict: {
                'type': 'full'|'eircode'|'postcode'|'partial',
                'full_address': str,
                'eircode': str|None,
                'county': str|None,
                'needs_clarification': bool,
                'suggestions': List[str]
            }
        """
        if not user_input or not user_input.strip():
            return {
                'type': 'missing',
                'full_address': '',
                'eircode': None,
                'county': None,
                'needs_clarification': True,
                'suggestions': ['Please provide the full address for the job']
            }
        
        cleaned_input = user_input.strip()
        result = {
            'type': 'unknown',
            'full_address': cleaned_input,
            'eircode': self.extract_eircode(cleaned_input),
            'county': self.extract_county(cleaned_input),
            'needs_clarification': False,
            'suggestions': []
        }
        
        # Check if it's just an eircode
        if self.is_postcode(cleaned_input) and self.validate_eircode(cleaned_input):
            result.update({
                'type': 'eircode',
                'eircode': self.normalize_eircode(cleaned_input),
                'needs_clarification': True,
                'suggestions': [
                    f"I have your eircode as {self.normalize_eircode(cleaned_input)}. Could you also give me the street address?"
                ]
            })
        
        # Check if it's a legacy postcode
        elif self.is_postcode(cleaned_input):
            result.update({
                'type': 'postcode',
                'needs_clarification': True,
                'suggestions': [
                    f"I have {cleaned_input} - could you give me the full street address as well?"
                ]
            })
        
        # Check if it's a full address
        elif len(cleaned_input.split()) >= 3:  # At least 3 words suggest full address
            result['type'] = 'full'
            
            # Still ask for eircode if not present
            if not result['eircode']:
                result['suggestions'].append("Do you have the eircode for that address?")
        
        # Partial address
        else:
            result.update({
                'type': 'partial',
                'needs_clarification': True,
                'suggestions': [
                    "Could you give me the full address including the town or city?",
                    "What town or city is that in?"
                ]
            })
        
        return result
    
    def format_address_confirmation(self, address_data: Dict) -> str:
        """
        Format address for confirmation with customer
        
        Args:
            address_data: Result from parse_address_input
            
        Returns:
            str: Formatted confirmation text
        """
        full_addr = address_data.get('full_address', '')
        eircode = address_data.get('eircode', '')
        
        if address_data['type'] == 'full':
            if eircode:
                return f"So that's {full_addr}, {eircode}?"
            else:
                return f"So that's {full_addr}?"
        elif address_data['type'] == 'eircode':
            return f"I have eircode {eircode} - could you also give me the street address?"
        elif address_data['type'] == 'postcode':
            return f"I have {full_addr} - could you give me the full street address as well?"
        else:
            return f"Could you give me the complete address including town and county?"
    
    def get_address_suggestions(self, address_data: Dict) -> List[str]:
        """Get suggestions for improving address data"""
        suggestions = []
        
        if not address_data.get('county'):
            suggestions.append("What county is that in?")
        
        if not address_data.get('eircode') and address_data['type'] != 'eircode':
            suggestions.append("Do you have the eircode for that address?")
        
        if address_data['type'] in ['partial', 'postcode']:
            suggestions.append("Could you give me the full street address?")
        
        return suggestions


def enhance_customer_address_lookup(customer_data: Dict, new_address_input: str) -> Dict:
    """
    Enhance customer lookup with address confirmation for returning customers
    
    Args:
        customer_data: Customer info from database lookup
        new_address_input: New address provided by customer
        
    Returns:
        dict: Enhanced customer data with address confirmation
    """
    validator = AddressValidator()
    
    # Get last known address from customer data
    last_address = customer_data.get('last_address', '')
    
    # Parse new address input if provided
    new_address_data = None
    if new_address_input:
        new_address_data = validator.parse_address_input(new_address_input)
    
    # Generate confirmation message
    if last_address and not new_address_input:
        # Ask if using same address
        return {
            **customer_data,
            'address_confirmation_needed': True,
            'suggested_response': f"I have your address as {last_address}. Is this job for the same location?"
        }
    elif last_address and new_address_input:
        # Compare addresses
        if new_address_input.lower().strip() in ['same', 'yes', 'correct', 'right']:
            return {
                **customer_data,
                'address_confirmed': True,
                'job_address': last_address
            }
        else:
            # New address provided
            return {
                **customer_data,
                'address_confirmed': True,
                'job_address': new_address_data['full_address'],
                'eircode': new_address_data.get('eircode'),
                'address_validation': new_address_data
            }
    
    return customer_data


# Utility functions for use in the main application
def validate_address_input(address_input: str) -> Dict:
    """Quick validation function for address input"""
    validator = AddressValidator()
    return validator.parse_address_input(address_input)


def format_address_for_confirmation(address_input: str) -> str:
    """Format address for customer confirmation"""
    validator = AddressValidator()
    address_data = validator.parse_address_input(address_input)
    return validator.format_address_confirmation(address_data)


def extract_eircode_from_text(text: str) -> Optional[str]:
    """Extract and normalize eircode from text"""
    validator = AddressValidator()
    return validator.extract_eircode(text)


def is_address_incomplete(address_input: str) -> bool:
    """Check if address input needs more information"""
    validator = AddressValidator()
    result = validator.parse_address_input(address_input)
    return result['needs_clarification']


def get_address_completion_prompt(address_input: str) -> Optional[str]:
    """Get prompt to complete incomplete address"""
    validator = AddressValidator()
    result = validator.parse_address_input(address_input)
    
    if result['needs_clarification'] and result['suggestions']:
        return result['suggestions'][0]
    
    return None