"""
Tests for eircode handling - ensuring eircodes are not duplicated
and returning customers with only eircodes are handled correctly.
"""
import pytest
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.address_validator import (
    AddressValidator,
    validate_address_input,
    extract_eircode_from_text,
)


class TestEircodeNotDuplicated:
    """Test that eircodes are not duplicated in address fields"""
    
    def test_eircode_only_input_standard_format(self):
        """When user provides just 'V95 H5P2', it should not be duplicated"""
        result = validate_address_input("V95 H5P2")
        
        assert result['type'] == 'eircode'
        assert result['eircode'] == 'V95 H5P2'
        # full_address should be the normalized eircode, not duplicated
        assert result['full_address'] == 'V95 H5P2'
        assert result['needs_clarification'] == False
    
    def test_eircode_only_input_no_space(self):
        """When user provides 'V95H5P2' without space"""
        result = validate_address_input("V95H5P2")
        
        assert result['type'] == 'eircode'
        assert result['eircode'] == 'V95 H5P2'  # Normalized with space
        assert result['full_address'] == 'V95 H5P2'
        assert result['needs_clarification'] == False
    
    def test_eircode_with_dashes_from_ai_spelling(self):
        """When AI spells back like 'V-9-5-H-5-P-2'"""
        result = validate_address_input("V-9-5-H-5-P-2")
        
        assert result['type'] == 'eircode'
        assert result['eircode'] == 'V95 H5P2'
        assert result['full_address'] == 'V95 H5P2'
        assert result['needs_clarification'] == False
    
    def test_eircode_dublin_format(self):
        """Dublin eircode like D02 WR97"""
        result = validate_address_input("D02 WR97")
        
        assert result['type'] == 'eircode'
        assert result['eircode'] == 'D02 WR97'
        assert result['full_address'] == 'D02 WR97'
        assert result['needs_clarification'] == False
    
    def test_eircode_with_asr_o_zero_confusion(self):
        """ASR sometimes confuses O and 0 - DO2 should become D02"""
        result = validate_address_input("DO2WR97")
        
        assert result['type'] == 'eircode'
        assert result['eircode'] == 'D02 WR97'  # O corrected to 0
        assert result['full_address'] == 'D02 WR97'


class TestFullAddressWithEircode:
    """Test full addresses that contain eircodes"""
    
    def test_full_address_with_eircode(self):
        """Full address like '32 Main Street, Ennis, Clare V95 H5P2'"""
        result = validate_address_input("32 Main Street, Ennis, Clare V95 H5P2")
        
        assert result['type'] == 'full'
        assert result['eircode'] == 'V95 H5P2'  # Extracted
        assert result['full_address'] == '32 Main Street, Ennis, Clare V95 H5P2'
        assert result['needs_clarification'] == False
    
    def test_full_address_without_eircode(self):
        """Full address without eircode"""
        result = validate_address_input("32 Main Street, Ennis, Clare")
        
        assert result['type'] == 'full'
        assert result['eircode'] is None
        assert result['full_address'] == '32 Main Street, Ennis, Clare'
        assert result['needs_clarification'] == False


class TestPartialAddress:
    """Test partial addresses that need clarification"""
    
    def test_partial_address_two_words(self):
        """Partial address like 'Main Street'"""
        result = validate_address_input("Main Street")
        
        assert result['type'] == 'partial'
        assert result['needs_clarification'] == True
    
    def test_single_word(self):
        """Single word like 'Ennis'"""
        result = validate_address_input("Ennis")
        
        assert result['type'] == 'partial'
        assert result['needs_clarification'] == True


class TestEircodeExtraction:
    """Test eircode extraction from various text formats"""
    
    def test_extract_from_full_address(self):
        """Extract eircode from full address"""
        eircode = extract_eircode_from_text("32 Main Street, Ennis V95 H5P2")
        assert eircode == 'V95 H5P2'
    
    def test_extract_from_eircode_only(self):
        """Extract from just eircode"""
        eircode = extract_eircode_from_text("V95H5P2")
        assert eircode == 'V95 H5P2'
    
    def test_no_eircode_present(self):
        """No eircode in text"""
        eircode = extract_eircode_from_text("32 Main Street, Ennis, Clare")
        assert eircode is None


class TestAddressValidatorMethods:
    """Test AddressValidator class methods directly"""
    
    def setup_method(self):
        self.validator = AddressValidator()
    
    def test_validate_eircode_valid(self):
        """Valid eircodes should pass validation"""
        assert self.validator.validate_eircode("V95H5P2") == True
        assert self.validator.validate_eircode("V95 H5P2") == True
        assert self.validator.validate_eircode("D02WR97") == True
        assert self.validator.validate_eircode("DO2WR97") == True  # O instead of 0
    
    def test_validate_eircode_invalid(self):
        """Invalid eircodes should fail validation"""
        assert self.validator.validate_eircode("") == False
        assert self.validator.validate_eircode("Dublin") == False
        assert self.validator.validate_eircode("12345") == False
    
    def test_normalize_eircode(self):
        """Eircode normalization"""
        assert self.validator.normalize_eircode("V95H5P2") == "V95 H5P2"
        assert self.validator.normalize_eircode("v95h5p2") == "V95 H5P2"  # Lowercase
        assert self.validator.normalize_eircode("DO2WR97") == "D02 WR97"  # O->0 fix
        assert self.validator.normalize_eircode("V-9-5-H-5-P-2") == "V95 H5P2"  # Dashes


class TestEdgeCases:
    """Test edge cases and potential issues"""
    
    def test_empty_input(self):
        """Empty input should be handled"""
        result = validate_address_input("")
        assert result['type'] == 'missing'
        assert result['needs_clarification'] == True
    
    def test_whitespace_only(self):
        """Whitespace only input"""
        result = validate_address_input("   ")
        assert result['type'] == 'missing'
        assert result['needs_clarification'] == True
    
    def test_none_input(self):
        """None input should be handled"""
        result = validate_address_input(None)
        assert result['type'] == 'missing'
        assert result['needs_clarification'] == True
    
    def test_numeric_code_accepted(self):
        """Short numeric codes should be accepted as eircode"""
        result = validate_address_input("123456")
        assert result['type'] == 'eircode'
        assert result['needs_clarification'] == False
    
    def test_asr_error_extra_char(self):
        """ASR sometimes adds extra characters like 'AV95H5P2'"""
        result = validate_address_input("AV95H5P2")
        # Should be accepted as eircode-like (6-8 alphanumeric with digits)
        assert result['type'] == 'eircode'
        assert result['needs_clarification'] == False


class TestBookingAddressFallback:
    """Test that booking fallback correctly retrieves eircode when address is None"""
    
    def test_booking_with_only_eircode(self):
        """Simulate a booking that only has eircode, no address"""
        booking = {
            'address': None,
            'eircode': 'V95 H5P2',
            'service_type': 'Plumbing'
        }
        
        # This is the pattern used in calendar_tools.py
        last_address = booking.get('address') or booking.get('eircode')
        assert last_address == 'V95 H5P2'
    
    def test_booking_with_address_and_eircode(self):
        """Booking with both address and eircode - address takes priority"""
        booking = {
            'address': '32 Main Street, Ennis',
            'eircode': 'V95 H5P2',
            'service_type': 'Plumbing'
        }
        
        last_address = booking.get('address') or booking.get('eircode')
        assert last_address == '32 Main Street, Ennis'
    
    def test_booking_with_neither(self):
        """Booking with neither address nor eircode"""
        booking = {
            'address': None,
            'eircode': None,
            'service_type': 'Plumbing'
        }
        
        last_address = booking.get('address') or booking.get('eircode')
        assert last_address is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
