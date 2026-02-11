"""
Test Service Matcher Logic

Tests the ServiceMatcher class for:
1. Exact name matching
2. Fuzzy matching with confidence scores
3. Fallback to General Service when confidence is low
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestServiceMatcherBasics:
    """Test basic ServiceMatcher functionality"""
    
    def test_service_matcher_import(self):
        """ServiceMatcher should be importable"""
        from src.services.calendar_tools import ServiceMatcher
        assert ServiceMatcher is not None
    
    def test_service_matcher_has_match_method(self):
        """ServiceMatcher should have match class method"""
        from src.services.calendar_tools import ServiceMatcher
        assert hasattr(ServiceMatcher, 'match')
        assert callable(ServiceMatcher.match)
    
    def test_service_matcher_has_tokenize_method(self):
        """ServiceMatcher should have tokenize class method"""
        from src.services.calendar_tools import ServiceMatcher
        assert hasattr(ServiceMatcher, 'tokenize')


class TestServiceMatching:
    """Test service matching logic using class methods"""
    
    def test_exact_match(self):
        """Exact service name should match with high confidence"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {'name': 'Plumbing Repair', 'price': 100, 'duration_minutes': 60},
            {'name': 'Electrical Work', 'price': 150, 'duration_minutes': 90}
        ]
        
        result = ServiceMatcher.match('Plumbing Repair', services)
        
        assert result is not None
        assert result.get('matched_name') == 'Plumbing Repair'
        assert result.get('score', 0) >= 80
    
    def test_case_insensitive_match(self):
        """Matching should be case insensitive"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {'name': 'Plumbing Repair', 'price': 100, 'duration_minutes': 60}
        ]
        
        result = ServiceMatcher.match('plumbing repair', services)
        
        assert result is not None
        assert result.get('matched_name') == 'Plumbing Repair'
    
    def test_partial_match(self):
        """Partial service name should still match"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {'name': 'Emergency Plumbing Repair', 'price': 200, 'duration_minutes': 120}
        ]
        
        result = ServiceMatcher.match('plumbing', services)
        
        assert result is not None
        assert result.get('score', 0) > 0
    
    def test_empty_input_returns_general(self):
        """Empty input should return General Service fallback"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {'name': 'Plumbing Repair', 'price': 100, 'duration_minutes': 60},
            {'name': 'General Service', 'price': 50, 'duration_minutes': 60}
        ]
        
        result = ServiceMatcher.match('', services)
        
        assert result is not None
        assert result.get('is_general', True)
    
    def test_none_input_handled(self):
        """None input should be handled gracefully"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {'name': 'Plumbing Repair', 'price': 100, 'duration_minutes': 60}
        ]
        
        result = ServiceMatcher.match(None, services)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_empty_services_list(self):
        """Empty services list should be handled"""
        from src.services.calendar_tools import ServiceMatcher
        
        result = ServiceMatcher.match('Plumbing', [])
        
        assert result is not None
        assert isinstance(result, dict)


class TestTokenization:
    """Test tokenization functionality"""
    
    def test_tokenize_basic(self):
        """Basic tokenization should work"""
        from src.services.calendar_tools import ServiceMatcher
        
        tokens = ServiceMatcher.tokenize('Plumbing Repair Service')
        
        assert isinstance(tokens, list)
        assert 'plumbing' in tokens or 'repair' in tokens
    
    def test_tokenize_removes_stop_words(self):
        """Tokenization should remove stop words"""
        from src.services.calendar_tools import ServiceMatcher
        
        tokens = ServiceMatcher.tokenize('the plumbing and repair')
        
        assert 'the' not in tokens
        assert 'and' not in tokens
    
    def test_tokenize_empty_string(self):
        """Empty string should return empty list"""
        from src.services.calendar_tools import ServiceMatcher
        
        tokens = ServiceMatcher.tokenize('')
        
        assert tokens == []
    
    def test_tokenize_none(self):
        """None should return empty list"""
        from src.services.calendar_tools import ServiceMatcher
        
        tokens = ServiceMatcher.tokenize(None)
        
        assert tokens == []


class TestFuzzyMatching:
    """Test fuzzy matching functionality"""
    
    def test_fuzzy_match_identical(self):
        """Identical strings should have score 1.0"""
        from src.services.calendar_tools import ServiceMatcher
        
        score = ServiceMatcher.fuzzy_match_score('Plumbing', 'Plumbing')
        
        assert score == 1.0
    
    def test_fuzzy_match_different(self):
        """Different strings should have low score"""
        from src.services.calendar_tools import ServiceMatcher
        
        score = ServiceMatcher.fuzzy_match_score('Plumbing', 'Electrical')
        
        assert score < 0.5


class TestNgramMatching:
    """Test n-gram matching functionality"""
    
    def test_ngram_similarity_identical(self):
        """Identical strings should have similarity 1.0"""
        from src.services.calendar_tools import ServiceMatcher
        
        score = ServiceMatcher.ngram_similarity('plumbing', 'plumbing')
        
        assert score == 1.0
    
    def test_ngram_similarity_different(self):
        """Different strings should have low similarity"""
        from src.services.calendar_tools import ServiceMatcher
        
        score = ServiceMatcher.ngram_similarity('plumbing', 'electrical')
        
        assert score < 0.5
    
    def test_get_ngrams(self):
        """Should generate correct n-grams"""
        from src.services.calendar_tools import ServiceMatcher
        
        ngrams = ServiceMatcher.get_ngrams('test', 3)
        
        assert isinstance(ngrams, set)
        assert 'tes' in ngrams
        assert 'est' in ngrams


class TestConfidenceThreshold:
    """Test confidence threshold behavior"""
    
    def test_high_confidence_match(self):
        """High confidence matches should return the service"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {'name': 'Plumbing Repair', 'price': 100, 'duration_minutes': 60}
        ]
        
        result = ServiceMatcher.match('Plumbing Repair', services)
        
        assert result is not None
        assert result.get('matched_name') == 'Plumbing Repair'
        assert result.get('score', 0) >= 80
    
    def test_threshold_constant_exists(self):
        """MATCH_THRESHOLD constant should exist"""
        from src.services.calendar_tools import ServiceMatcher
        
        assert hasattr(ServiceMatcher, 'MATCH_THRESHOLD')
        assert ServiceMatcher.MATCH_THRESHOLD == 35


class TestEdgeCases:
    """Test edge cases in service matching"""
    
    def test_special_characters(self):
        """Should handle special characters"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {'name': 'Plumbing Repair', 'price': 100, 'duration_minutes': 60}
        ]
        
        result = ServiceMatcher.match('Plumbing!!! @#$%', services)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_long_input(self):
        """Should handle long input strings"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {'name': 'Plumbing Repair', 'price': 100, 'duration_minutes': 60}
        ]
        
        long_input = 'plumbing ' * 100
        result = ServiceMatcher.match(long_input, services)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_numeric_input(self):
        """Should handle numeric input"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {'name': 'Plumbing Repair', 'price': 100, 'duration_minutes': 60}
        ]
        
        result = ServiceMatcher.match('12345', services)
        
        assert result is not None
        assert isinstance(result, dict)


class TestCalculateMatchScore:
    """Test the calculate_match_score method"""
    
    def test_exact_match_score(self):
        """Exact match should return 100"""
        from src.services.calendar_tools import ServiceMatcher
        
        service = {'name': 'Plumbing Repair', 'description': '', 'category': ''}
        score, details = ServiceMatcher.calculate_match_score('Plumbing Repair', service)
        
        assert score == 100
        assert details['type'] == 'exact'
    
    def test_partial_match_score(self):
        """Partial match should return lower score"""
        from src.services.calendar_tools import ServiceMatcher
        
        service = {'name': 'Plumbing Repair', 'description': '', 'category': ''}
        score, details = ServiceMatcher.calculate_match_score('plumbing', service)
        
        assert score > 0
        assert score < 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
