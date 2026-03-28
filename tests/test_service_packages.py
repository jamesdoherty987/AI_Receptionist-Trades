"""
Test Service Packages Feature

Tests the full packages pipeline:
1. ServiceMatcher with packages (fuzzy matching, confidence tiers)
2. Package-only service filtering
3. Uncertainty fallback behavior
4. Clarifying question propagation
5. Prompt generation with packages
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.calendar_tools import ServiceMatcher


# ============================================================
# Test Data Fixtures
# ============================================================

SAMPLE_SERVICES = [
    {'id': 'svc_1', 'name': 'Toilet Leak Repair', 'description': 'Fix leaking toilets', 'category': 'Plumbing', 'price': 80, 'duration_minutes': 60},
    {'id': 'svc_2', 'name': 'Pipe Replacement', 'description': 'Replace damaged pipes', 'category': 'Plumbing', 'price': 150, 'duration_minutes': 120},
    {'id': 'svc_3', 'name': 'General Service', 'description': 'General callout', 'category': 'General', 'price': 60, 'duration_minutes': 1440},
    {'id': 'svc_4', 'name': 'Toilet Replacement', 'description': 'Full toilet replacement', 'category': 'Plumbing', 'price': 200, 'duration_minutes': 180},
]

PACKAGE_ONLY_SERVICE = {
    'id': 'svc_inspect', 'name': 'Roof Inspection', 'description': 'Inspect roof for damage',
    'category': 'Roofing', 'price': 50, 'duration_minutes': 60, 'package_only': True
}

SAMPLE_PACKAGES = [
    {
        'id': 'pkg_1',
        'name': 'Roof Leak Investigation',
        'description': 'Complete roof leak diagnosis and repair for unknown leak sources',
        'services': [
            {'service_id': 'svc_inspect', 'name': 'Roof Inspection', 'duration_minutes': 60, 'price': 50, 'sort_order': 0},
            {'service_id': 'svc_find', 'name': 'Leak Finding', 'duration_minutes': 90, 'price': 100, 'sort_order': 1},
            {'service_id': 'svc_fix', 'name': 'Roof Repair', 'duration_minutes': 120, 'price': 150, 'sort_order': 2},
        ],
        'use_when_uncertain': True,
        'clarifying_question': 'Do you know where the leak is coming from?',
        'price_override': None,
        'price_max_override': None,
        'total_duration_minutes': 270,
        'duration_label': '4.5 hours',
        'total_price': 300,
        'total_price_max': 300,
    }
]


# ============================================================
# Basic Package Matching
# ============================================================

class TestPackageMatching:
    """Test that packages are matched alongside services"""

    def test_exact_package_name_match(self):
        """Exact package name should match with high confidence"""
        result = ServiceMatcher.match('Roof Leak Investigation', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        assert result['matched_name'] == 'Roof Leak Investigation'
        assert result.get('is_package') == True
        assert result['score'] >= 80

    def test_package_description_helps_matching(self):
        """Package description + service names should help matching"""
        result = ServiceMatcher.match('roof leak unknown source', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        # Should match the package since its description mentions "unknown leak sources"
        # and its services include "Leak Finding"
        assert result is not None
        assert result['score'] > 0

    def test_clear_service_match_beats_package(self):
        """A clear service match should beat a vague package match"""
        result = ServiceMatcher.match('Toilet Leak Repair', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        assert result['matched_name'] == 'Toilet Leak Repair'
        assert not result.get('is_package', False)
        assert result['score'] >= 80

    def test_package_duration_is_sum_of_services(self):
        """When a package matches, duration should be the sum of constituent services"""
        result = ServiceMatcher.match('Roof Leak Investigation', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        assert result['service']['duration_minutes'] == 270  # 60 + 90 + 120

    def test_no_packages_backward_compatible(self):
        """When no packages provided, matching works exactly as before"""
        result = ServiceMatcher.match('Toilet Leak Repair', SAMPLE_SERVICES)
        assert result['matched_name'] == 'Toilet Leak Repair'
        assert result['score'] >= 80
        assert not result.get('is_package', False)

    def test_empty_packages_list(self):
        """Empty packages list should work fine"""
        result = ServiceMatcher.match('Toilet Leak Repair', SAMPLE_SERVICES, packages=[])
        assert result['matched_name'] == 'Toilet Leak Repair'


# ============================================================
# Package-Only Service Filtering
# ============================================================

class TestPackageOnlyFiltering:
    """Test that package_only services are excluded from standalone matching"""

    def test_package_only_excluded_from_standalone(self):
        """package_only services should never be returned as standalone matches"""
        services_with_pkg_only = SAMPLE_SERVICES + [PACKAGE_ONLY_SERVICE]
        result = ServiceMatcher.match('Roof Inspection', services_with_pkg_only, packages=[])
        # Should NOT match the package_only service
        assert result.get('matched_name') != 'Roof Inspection'

    def test_non_package_only_still_matches(self):
        """Regular services should still match normally"""
        services_with_pkg_only = SAMPLE_SERVICES + [PACKAGE_ONLY_SERVICE]
        result = ServiceMatcher.match('Toilet Leak Repair', services_with_pkg_only, packages=[])
        assert result['matched_name'] == 'Toilet Leak Repair'


# ============================================================
# Confidence Tier Classification
# ============================================================

class TestConfidenceTiers:
    """Test confidence tier assignment"""

    def test_high_confidence_tier(self):
        """Exact match should be high confidence"""
        result = ServiceMatcher.match('Toilet Leak Repair', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        assert result.get('confidence_tier') == 'high'
        assert result.get('needs_clarification') == False

    def test_high_confidence_no_clarification(self):
        """High confidence should not need clarification"""
        result = ServiceMatcher.match('Toilet Replacement', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        assert result.get('confidence_tier') == 'high'
        assert result.get('needs_clarification') == False

    def test_grey_zone_with_ambiguous_input(self):
        """Ambiguous input matching multiple candidates should be grey zone"""
        # "leak" could match Toilet Leak Repair AND Roof Leak Investigation package
        result = ServiceMatcher.match('leak', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        # Should have some match (not general)
        assert result['score'] >= 35
        # If multiple close matches exist, should be grey zone
        if result.get('confidence_tier') == 'grey_zone':
            assert result.get('needs_clarification') == True
            assert 'close_matches' in result

    def test_low_confidence_fallback(self):
        """Very vague input should be low confidence"""
        result = ServiceMatcher.match('something is wrong with my house', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        # Should be low confidence or general fallback
        assert result.get('confidence_tier') in ('low', 'grey_zone') or result.get('is_general', False)

    def test_confidence_tier_always_present(self):
        """Every result should have a confidence_tier"""
        for desc in ['Toilet Leak Repair', 'leak', 'xyz random stuff', '']:
            result = ServiceMatcher.match(desc, SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
            assert 'confidence_tier' in result, f"Missing confidence_tier for '{desc}'"


# ============================================================
# Clarifying Question Propagation
# ============================================================

class TestClarifyingQuestions:
    """Test that clarifying questions propagate correctly"""

    def test_suggested_question_in_grey_zone(self):
        """Grey zone with uncertain package should include suggested_question"""
        result = ServiceMatcher.match('leak', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        if result.get('confidence_tier') == 'grey_zone':
            # The Roof Leak Investigation package has a clarifying question
            assert 'suggested_question' in result or 'close_matches' in result

    def test_no_question_for_high_confidence(self):
        """High confidence matches should not have suggested_question"""
        result = ServiceMatcher.match('Toilet Leak Repair', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        assert result.get('confidence_tier') == 'high'
        assert 'suggested_question' not in result


# ============================================================
# Uncertainty Package Fallback
# ============================================================

class TestUncertaintyFallback:
    """Test use_when_uncertain package behavior"""

    def test_uncertain_package_tagged(self):
        """Package with use_when_uncertain should have the flag in virtual entry"""
        result = ServiceMatcher.match('Roof Leak Investigation', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        assert result['service'].get('use_when_uncertain') == True

    def test_package_without_uncertain_flag(self):
        """Package without use_when_uncertain should not have the flag"""
        non_uncertain_pkg = [{
            'id': 'pkg_2',
            'name': 'Full Bathroom Renovation',
            'description': 'Complete bathroom overhaul',
            'services': [
                {'service_id': 's1', 'name': 'Plumbing Assessment', 'duration_minutes': 60, 'price': 50, 'sort_order': 0},
                {'service_id': 's2', 'name': 'Tiling', 'duration_minutes': 480, 'price': 300, 'sort_order': 1},
            ],
            'use_when_uncertain': False,
            'clarifying_question': None,
        }]
        result = ServiceMatcher.match('Full Bathroom Renovation', SAMPLE_SERVICES, packages=non_uncertain_pkg)
        assert result['service'].get('use_when_uncertain', False) == False


# ============================================================
# Prompt Builder Tests
# ============================================================

class TestPromptBuilder:
    """Test the _build_packages_prompt_section function"""

    def test_build_packages_prompt_empty(self):
        """Empty packages should return empty string"""
        from src.services.llm_stream import _build_packages_prompt_section
        assert _build_packages_prompt_section([]) == ""
        assert _build_packages_prompt_section(None) == ""

    def test_build_packages_prompt_basic(self):
        """Should build correct prompt section"""
        from src.services.llm_stream import _build_packages_prompt_section
        result = _build_packages_prompt_section(SAMPLE_PACKAGES)
        assert '📦 Roof Leak Investigation' in result
        assert '[USE WHEN ISSUE IS UNCERTAIN]' in result
        assert 'Roof Inspection → Leak Finding → Roof Repair' in result

    def test_build_packages_prompt_no_uncertain_tag(self):
        """Package without use_when_uncertain should not have the tag"""
        from src.services.llm_stream import _build_packages_prompt_section
        pkgs = [{
            'id': 'pkg_2',
            'name': 'Garden Transformation',
            'services': [
                {'name': 'Design', 'duration_minutes': 60, 'price': 50, 'sort_order': 0},
                {'name': 'Planting', 'duration_minutes': 120, 'price': 100, 'sort_order': 1},
            ],
            'use_when_uncertain': False,
            'clarifying_question': None,
            'total_price': 150,
            'total_price_max': 150,
            'duration_label': '3 hours',
        }]
        result = _build_packages_prompt_section(pkgs)
        assert '📦 Garden Transformation' in result
        assert '[USE WHEN ISSUE IS UNCERTAIN]' not in result
        assert 'Ask:' not in result

    def test_build_packages_prompt_price_range(self):
        """Should show price range when max > min"""
        from src.services.llm_stream import _build_packages_prompt_section
        pkgs = [{
            'id': 'pkg_3',
            'name': 'Test Package',
            'services': [
                {'name': 'Svc1', 'duration_minutes': 60, 'price': 50, 'sort_order': 0},
                {'name': 'Svc2', 'duration_minutes': 60, 'price': 50, 'sort_order': 1},
            ],
            'use_when_uncertain': False,
            'clarifying_question': None,
            'total_price': 100,
            'total_price_max': 200,
            'duration_label': '2 hours',
        }]
        result = _build_packages_prompt_section(pkgs)
        assert '€100 to €200' in result


# ============================================================
# Edge Cases
# ============================================================

class TestEdgeCases:
    """Test edge cases in package matching"""

    def test_empty_services_with_packages(self):
        """Should handle empty services list with packages"""
        result = ServiceMatcher.match('Roof Leak Investigation', [], packages=SAMPLE_PACKAGES)
        assert result is not None
        # Should match the package even with no standalone services
        assert result.get('matched_name') == 'Roof Leak Investigation'

    def test_none_packages(self):
        """None packages should work (backward compat)"""
        result = ServiceMatcher.match('Toilet Leak Repair', SAMPLE_SERVICES, packages=None)
        assert result['matched_name'] == 'Toilet Leak Repair'

    def test_package_with_empty_services(self):
        """Package with empty services list should still be scored by name"""
        empty_pkg = [{
            'id': 'pkg_empty',
            'name': 'Empty Package',
            'description': 'A package with no services',
            'services': [],
            'use_when_uncertain': False,
            'clarifying_question': None,
        }]
        result = ServiceMatcher.match('Empty Package', SAMPLE_SERVICES, packages=empty_pkg)
        # Should still match by name
        assert result is not None

    def test_special_characters_in_package_name(self):
        """Should handle special characters gracefully"""
        result = ServiceMatcher.match('Roof Leak Investigation!!!', SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        assert result is not None

    def test_very_long_description(self):
        """Should handle very long job descriptions"""
        long_desc = 'roof leak ' * 100
        result = ServiceMatcher.match(long_desc, SAMPLE_SERVICES, packages=SAMPLE_PACKAGES)
        assert result is not None


# ============================================================
# Settings Manager Package Methods (unit tests without DB)
# ============================================================

class TestPackageDurationCalculation:
    """Test calculate_package_duration logic"""

    def test_duration_sum(self):
        """Duration should be sum of service durations"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)  # Skip __init__
        
        pkg = {
            'services': [
                {'duration_minutes': 60, 'price': 50},
                {'duration_minutes': 90, 'price': 100},
                {'duration_minutes': 120, 'price': 150},
            ]
        }
        result = mgr.calculate_package_duration(pkg)
        assert result['min_minutes'] == 270
        assert result['label'] != ''

    def test_duration_empty_services(self):
        """Empty services should return 0 duration"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)
        
        pkg = {'services': []}
        result = mgr.calculate_package_duration(pkg)
        assert result['min_minutes'] == 0


class TestPackagePriceCalculation:
    """Test calculate_package_price logic"""

    def test_price_sum_no_override(self):
        """Without override, price should be sum of services"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)
        
        pkg = {
            'services': [
                {'price': 50, 'price_max': 70},
                {'price': 100, 'price_max': 130},
            ],
            'price_override': None,
            'price_max_override': None,
        }
        result = mgr.calculate_package_price(pkg)
        assert result['price'] == 150
        assert result['price_max'] == 200

    def test_price_with_override(self):
        """With override, should use override value"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)
        
        pkg = {
            'services': [
                {'price': 50},
                {'price': 100},
            ],
            'price_override': 120,
            'price_max_override': 180,
        }
        result = mgr.calculate_package_price(pkg)
        assert result['price'] == 120
        assert result['price_max'] == 180


class TestPackageValidation:
    """Test _validate_package_data logic"""

    def test_valid_package(self):
        """Valid package data should pass validation"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)
        # Can't fully test without DB, but we can test name/services count validation
        
        # Missing name
        error = mgr._validate_package_data({'name': '', 'services': []})
        assert error is not None
        assert 'name' in error.lower()

    def test_too_few_services(self):
        """Package with < 2 services should fail"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)
        
        error = mgr._validate_package_data({
            'name': 'Test',
            'services': [{'service_id': 'svc_1'}]
        })
        assert error is not None
        assert '2' in error

    def test_name_too_long(self):
        """Package name > 200 chars should fail"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)
        
        error = mgr._validate_package_data({
            'name': 'x' * 201,
            'services': [{'service_id': 'a'}, {'service_id': 'b'}]
        })
        assert error is not None
        assert '200' in error

    def test_duplicate_service_ids(self):
        """Duplicate service_ids should fail"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)
        
        error = mgr._validate_package_data({
            'name': 'Test',
            'services': [{'service_id': 'svc_1'}, {'service_id': 'svc_1'}]
        })
        assert error is not None
        assert 'duplicate' in error.lower()

    def test_clarifying_question_too_long(self):
        """Clarifying question > 500 chars should fail"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)
        
        error = mgr._validate_package_data({
            'name': 'Test',
            'services': [{'service_id': 'a'}, {'service_id': 'b'}],
            'clarifying_question': 'x' * 501
        })
        assert error is not None
        assert '500' in error

    def test_negative_price_override(self):
        """Negative price override should fail"""
        from src.services.settings_manager import SettingsManager
        mgr = SettingsManager.__new__(SettingsManager)
        
        error = mgr._validate_package_data({
            'name': 'Test',
            'services': [{'service_id': 'a'}, {'service_id': 'b'}],
            'price_override': -10
        })
        assert error is not None
        assert 'non-negative' in error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
