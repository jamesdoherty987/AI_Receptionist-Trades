"""
Service matching engine for calendar operations.

Extracted from calendar_tools.py for maintainability.
Contains: ServiceMatcher, AIServiceMatcher, and convenience functions
(lookup_service_by_name, match_service, get_service_price, etc.)
"""

import logging

logger = logging.getLogger(__name__)


class ServiceMatcher:
    """
    Intelligent service matching using multiple strategies.
    
    Scalable approach that works with any services without hardcoded values:
    1. Exact/substring matching (fastest)
    2. Fuzzy string matching using difflib (handles typos)
    3. Token-based TF-IDF style scoring (semantic similarity)
    4. N-gram matching (catches partial word matches)
    
    Falls back to "General Service" when confidence is low.
    """
    
    # Common English stop words to ignore in matching
    # NOTE: Do NOT add domain-specific words here (paint, electrical, pipe, etc.)
    # Only add truly generic words that don't help distinguish services
    STOP_WORDS = frozenset([
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
        'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
        'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
        'because', 'until', 'while', 'although', 'though', 'after', 'before',
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you',
        'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
        'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them',
        'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this',
        'that', 'these', 'those', 'am', 'been', 'being', 'got', 'get', 'getting',
        # Generic job/service words that don't help with matching
        'work', 'works', 'working', 'job', 'jobs', 'service', 'services',
        'help', 'helps', 'helping', 'needed', 'needs', 'want', 'wants',
        'like', 'please', 'thanks', 'thank', 'done', 'complete', 'completed'
    ])
    
    # Minimum confidence threshold for a match (0-100)
    MATCH_THRESHOLD = 35
    
    @classmethod
    def tokenize(cls, text: str) -> list:
        """
        Tokenize text into meaningful words, removing stop words.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of meaningful tokens
        """
        import re
        if not text:
            return []
        
        # Convert to lowercase and extract words (3+ chars)
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        
        # Remove stop words
        return [w for w in words if w not in cls.STOP_WORDS]
    
    @classmethod
    def get_ngrams(cls, text: str, n: int = 3) -> set:
        """
        Generate character n-grams from text for fuzzy matching.
        
        Args:
            text: Input text
            n: N-gram size (default 3 for trigrams)
            
        Returns:
            Set of n-grams
        """
        text = text.lower().replace(' ', '')
        if len(text) < n:
            return {text}
        return {text[i:i+n] for i in range(len(text) - n + 1)}
    
    @classmethod
    def ngram_similarity(cls, text1: str, text2: str, n: int = 3) -> float:
        """
        Calculate n-gram similarity between two strings.
        
        Args:
            text1: First string
            text2: Second string
            n: N-gram size
            
        Returns:
            Similarity score (0-1)
        """
        ngrams1 = cls.get_ngrams(text1, n)
        ngrams2 = cls.get_ngrams(text2, n)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        
        return intersection / union if union > 0 else 0.0
    
    @classmethod
    def fuzzy_match_score(cls, text1: str, text2: str) -> float:
        """
        Calculate fuzzy match score using multiple methods.
        
        Args:
            text1: First string
            text2: Second string
            
        Returns:
            Combined similarity score (0-1)
        """
        from difflib import SequenceMatcher
        
        if not text1 or not text2:
            return 0.0
        
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        # Method 1: Sequence matcher (handles insertions, deletions, substitutions)
        seq_score = SequenceMatcher(None, text1_lower, text2_lower).ratio()
        
        # Method 2: N-gram similarity (handles partial matches)
        ngram_score = cls.ngram_similarity(text1_lower, text2_lower)
        
        # Combine scores (weighted average)
        return (seq_score * 0.6) + (ngram_score * 0.4)
    
    @classmethod
    def token_overlap_score(cls, tokens1: list, tokens2: list) -> float:
        """
        Calculate token overlap score with TF-IDF style weighting.
        
        Longer/rarer words get higher weight.
        
        Args:
            tokens1: First token list
            tokens2: Second token list
            
        Returns:
            Weighted overlap score (0-1)
        """
        if not tokens1 or not tokens2:
            return 0.0
        
        set1 = set(tokens1)
        set2 = set(tokens2)
        
        # Find matching tokens
        matches = set1 & set2
        
        if not matches:
            return 0.0
        
        # Weight by token length (longer words are more specific)
        weighted_match_score = sum(len(t) for t in matches)
        max_possible = sum(len(t) for t in set1 | set2)
        
        return weighted_match_score / max_possible if max_possible > 0 else 0.0
    
    @classmethod
    def calculate_match_score(cls, job_description: str, service: dict) -> tuple:
        """
        Calculate comprehensive match score between job description and service.
        
        Prioritizes service NAME matches over description matches.
        
        Args:
            job_description: The job description from customer
            service: Service dict with name, description, category
            
        Returns:
            Tuple of (score 0-100, match_details dict)
        """
        service_name = (service.get('name') or '').strip()
        service_desc = (service.get('description') or '').strip()
        service_category = (service.get('category') or '').strip()
        
        # Build tags string for matching
        tags = service.get('tags')
        if isinstance(tags, str):
            try:
                import json as _jt
                tags = _jt.loads(tags)
            except Exception:
                tags = []
        tags_str = ' '.join(tags) if isinstance(tags, list) else ''
        
        job_lower = job_description.lower().strip()
        name_lower = service_name.lower()
        desc_lower = service_desc.lower()
        
        # Tokenize job description
        job_tokens = cls.tokenize(job_description)
        
        # Tokenize service name ONLY (prioritize name matches)
        name_tokens = cls.tokenize(service_name)
        
        # Tokenize description separately
        desc_tokens = cls.tokenize(service_desc)
        
        # Tokenize full service text (name + description + category + tags)
        service_text = f"{service_name} {service_desc} {service_category} {tags_str}"
        service_tokens = cls.tokenize(service_text)
        
        score = 0
        match_type = "none"
        
        # Strategy 1: Exact match (100 points)
        if job_lower == name_lower:
            return (100, {"type": "exact", "matched": service_name})
        
        # Strategy 2: Substring match (85-95 points)
        if name_lower in job_lower:
            score = 95
            match_type = "name_in_job"
        elif job_lower in name_lower:
            score = 90
            match_type = "job_in_name"
        elif len(name_lower) > 4 and any(name_lower in job_lower.replace(' ', '') for _ in [1]):
            # Check without spaces (e.g., "pipe repair" matches "piperepair")
            score = 85
            match_type = "substring_nospace"
        
        if score >= 85:
            return (score, {"type": match_type, "matched": service_name})
        
        # Strategy 3: NAME token overlap (up to 85 points) - PRIORITIZED
        name_token_score = cls.token_overlap_score(job_tokens, name_tokens)
        if name_token_score > 0:
            # Scale to 0-85 range (higher than description matches)
            name_token_points = int(name_token_score * 85)
            if name_token_points > score:
                score = name_token_points
                match_type = "name_token_overlap"
        
        # Strategy 4: Fuzzy name match (up to 80 points)
        fuzzy_name_score = cls.fuzzy_match_score(job_description, service_name)
        if fuzzy_name_score > 0.5:  # Only consider if reasonably similar
            fuzzy_points = int(fuzzy_name_score * 80)
            if fuzzy_points > score:
                score = fuzzy_points
                match_type = "fuzzy_name"
        
        # Strategy 5: Description keyword match (up to 75 points)
        # Check if job description words appear in service description
        # This helps differentiate similar services (Interior vs Exterior Painting)
        desc_token_score = cls.token_overlap_score(job_tokens, desc_tokens)
        if desc_token_score > 0:
            desc_token_points = int(desc_token_score * 75)
            if desc_token_points > score:
                score = desc_token_points
                match_type = "desc_token_overlap"
        
        # Strategy 6: Full token overlap including description (up to 70 points)
        token_score = cls.token_overlap_score(job_tokens, service_tokens)
        if token_score > 0:
            # Scale to 0-70 range (lower than name-only matches)
            token_points = int(token_score * 70)
            if token_points > score:
                score = token_points
                match_type = "token_overlap"
        
        # Strategy 7: Fuzzy description match (up to 55 points)
        if service_desc:
            fuzzy_desc_score = cls.fuzzy_match_score(job_description, service_desc)
            if fuzzy_desc_score > 0.4:
                fuzzy_desc_points = int(fuzzy_desc_score * 55)
                if fuzzy_desc_points > score:
                    score = fuzzy_desc_points
                    match_type = "fuzzy_description"
        
        # Strategy 8: Category match bonus (+10 points)
        if service_category and service_category.lower() in job_lower:
            score = min(100, score + 10)
            match_type = f"{match_type}+category"
        
        # Strategy 9: Individual word fuzzy match against NAME ONLY (catches typos)
        # Only match against service name tokens, not description
        if score < cls.MATCH_THRESHOLD:
            for job_word in job_tokens:
                if len(job_word) >= 4:  # Only check meaningful words
                    for name_word in name_tokens:
                        if len(name_word) >= 4:
                            word_similarity = cls.fuzzy_match_score(job_word, name_word)
                            # Lower threshold (0.6) to catch word variations like paint/painting
                            if word_similarity > 0.6:
                                word_score = int(word_similarity * 60)
                                if word_score > score:
                                    score = word_score
                                    match_type = f"name_word_match:{job_word}~{name_word}"
        
        # Strategy 10: Stem matching - check if job word is prefix of name word or vice versa
        # This catches paint->painting, electric->electrical, plumber->plumbing, etc.
        if score < cls.MATCH_THRESHOLD:
            for job_word in job_tokens:
                if len(job_word) >= 4:
                    for name_word in name_tokens:
                        if len(name_word) >= 4:
                            # Check if one is prefix of the other (stem match)
                            if name_word.startswith(job_word) or job_word.startswith(name_word):
                                stem_score = 50  # Good match for stem
                                if stem_score > score:
                                    score = stem_score
                                    match_type = f"stem_match:{job_word}~{name_word}"
                            # Check if they share a common stem (4+ chars)
                            # This catches plumber/plumbing, painter/painting, etc.
                            elif len(job_word) >= 5 and len(name_word) >= 5:
                                common_len = 0
                                for k in range(min(len(job_word), len(name_word))):
                                    if job_word[k] == name_word[k]:
                                        common_len += 1
                                    else:
                                        break
                                if common_len >= 4:
                                    stem_score = 45  # Slightly lower than direct prefix
                                    if stem_score > score:
                                        score = stem_score
                                        match_type = f"common_stem:{job_word[:common_len]}~{job_word}/{name_word}"
        
        # Strategy 11: Description keyword bonus when name matches are tied
        # If we have a name match, check description for differentiating keywords
        # Also check for stem/plural matches (fence/fences, wall/walls)
        if score >= cls.MATCH_THRESHOLD and desc_tokens:
            desc_overlap = set(job_tokens) & set(desc_tokens)
            
            # Also check for stem matches in description
            for job_word in job_tokens:
                if len(job_word) >= 4:
                    for desc_word in desc_tokens:
                        if len(desc_word) >= 4:
                            # Check if one is prefix of the other (stem/plural match)
                            if desc_word.startswith(job_word) or job_word.startswith(desc_word):
                                desc_overlap.add(job_word)
            
            if desc_overlap:
                # Add bonus for description keyword matches
                bonus = min(15, len(desc_overlap) * 5)
                score = min(100, score + bonus)
                match_type = f"{match_type}+desc_bonus"
        
        return (score, {"type": match_type, "matched": service_name, "tokens_matched": len(set(job_tokens) & set(service_tokens))})
    
    @classmethod
    def match(cls, job_description: str, services: list, default_duration: int = 1440, packages: list = None) -> dict:
        """
        Match a job description to the best service or package.
        
        Args:
            job_description: Description of the job from customer
            services: List of service dicts from database
            default_duration: Default duration if no match found (1 day for trades)
            packages: Optional list of resolved package dicts for unified scoring
            
        Returns:
            Dict with matched service info, including confidence_tier and
            needs_clarification fields when packages are in the pool.
        """
        if not job_description or not job_description.strip():
            return cls._create_general_fallback(services, default_duration, "empty_description")
        
        # Filter out package_only services from standalone matching
        standalone_services = [s for s in services if not s.get('package_only', False)]
        
        # Convert packages to virtual service entries for unified scoring
        virtual_entries = []
        if packages:
            for pkg in packages:
                pkg_services = pkg.get('services', [])
                service_names = [s.get('name', '') for s in pkg_services]
                combined_desc = f"{pkg.get('description', '')} {' '.join(service_names)}"
                duration = pkg.get('duration_override') or pkg.get('total_duration_minutes') or sum(s.get('duration_minutes', 0) for s in pkg_services)
                price = pkg.get('price_override') or pkg.get('total_price') or sum(s.get('price', 0) for s in pkg_services)
                
                virtual_entries.append({
                    'id': pkg['id'],
                    'name': pkg['name'],
                    'description': combined_desc,
                    'category': 'Package',
                    'duration_minutes': duration,
                    'price': price,
                    'is_package': True,
                    'use_when_uncertain': pkg.get('use_when_uncertain', False),
                    'clarifying_question': pkg.get('clarifying_question'),
                    '_package_data': pkg
                })
        
        # Combine standalone services and virtual package entries
        all_candidates = standalone_services + virtual_entries
        
        best_match = None
        best_score = 0
        best_details = {}
        general_service = None
        all_scores = []
        
        for service in all_candidates:
            service_name = (service.get('name') or '').lower()
            service_category = (service.get('category') or '').lower()
            
            # Track General service for fallback
            if 'general' in service_name or service_category == 'general':
                general_service = service
                continue  # Don't match against General service directly
            
            score, details = cls.calculate_match_score(job_description, service)
            all_scores.append({'candidate': service, 'score': score, 'details': details})
            
            if score > best_score:
                best_score = score
                best_match = service
                best_details = details
        
        # Check if match meets threshold
        if best_match and best_score >= cls.MATCH_THRESHOLD:
            matched_name = best_match.get('name', 'Unknown')
            logger.debug(f"Service match: '{job_description}' -> '{matched_name}' (score: {best_score}, type: {best_details.get('type', 'unknown')})")
            result = {
                'service': best_match,
                'score': best_score,
                'matched_name': matched_name,
                'match_details': best_details,
                'is_general': False
            }
            
            # Tag package results
            if best_match.get('is_package'):
                result['is_package'] = True
            
            # Add confidence tier classification
            result.update(cls._classify_confidence(best_score, all_scores))
            
            return result
        
        # Fall back to General service
        fallback = cls._create_general_fallback(
            standalone_services, 
            default_duration, 
            f"low_score:{best_score}" if best_match else "no_services",
            general_service
        )
        # Add low confidence tier to fallback
        fallback['confidence_tier'] = 'low'
        fallback['needs_clarification'] = False
        return fallback
    
    @classmethod
    def _classify_confidence(cls, best_score: int, all_scores: list) -> dict:
        """
        Classify match confidence into tiers and identify close matches.
        
        Args:
            best_score: The top match score
            all_scores: List of dicts with 'candidate', 'score', 'details' for all scored candidates
            
        Returns:
            Dict with confidence_tier, needs_clarification, and optionally close_matches/suggested_question
        """
        result = {}
        
        if best_score >= 80:
            result['confidence_tier'] = 'high'
            result['needs_clarification'] = False
            return result
        
        # Collect close matches: scored within 30 points of top AND >= 40
        close_matches = [
            entry for entry in all_scores
            if entry['score'] >= best_score - 30 and entry['score'] >= 40
        ]
        close_matches.sort(key=lambda x: x['score'], reverse=True)
        
        if best_score >= 40 and len(close_matches) >= 2:
            result['confidence_tier'] = 'grey_zone'
            result['needs_clarification'] = True
            result['close_matches'] = [
                {'candidate': cm['candidate'], 'score': cm['score']}
                for cm in close_matches[:3]
            ]
            # Check for suggested question from uncertain package
            for cm in close_matches:
                candidate = cm['candidate']
                if candidate.get('use_when_uncertain') and candidate.get('clarifying_question'):
                    result['suggested_question'] = candidate['clarifying_question']
                    break
        else:
            result['confidence_tier'] = 'low'
            result['needs_clarification'] = False
        
        return result
    
    @classmethod
    def _create_general_fallback(cls, services: list, default_duration: int, reason: str, general_service: dict = None) -> dict:
        """Create a General service fallback response."""
        from src.utils.config import config
        
        # Get default charge from config
        default_charge = getattr(config, 'DEFAULT_APPOINTMENT_CHARGE', 50.0)
        
        # Use existing General service if available
        if general_service:
            # Ensure General service has a price (use default if not set)
            if not general_service.get('price') or general_service.get('price') == 0:
                general_service = dict(general_service)  # Make a copy
                general_service['price'] = default_charge
            logger.debug(f"Using General Service (reason: {reason})")
            return {
                'service': general_service,
                'score': 0,
                'matched_name': general_service.get('name', 'General Service'),
                'match_details': {'type': 'fallback', 'reason': reason},
                'is_general': True,
                'confidence_tier': 'low',
                'needs_clarification': False
            }
        
        # Find General service in list
        for service in services:
            service_name = (service.get('name') or '').lower()
            service_category = (service.get('category') or '').lower()
            if 'general' in service_name or service_category == 'general':
                # Ensure it has a price
                if not service.get('price') or service.get('price') == 0:
                    service = dict(service)  # Make a copy
                    service['price'] = default_charge
                logger.debug(f"Using General Service (reason: {reason})")
                return {
                    'service': service,
                    'score': 0,
                    'matched_name': service.get('name', 'General Callout'),
                    'match_details': {'type': 'fallback', 'reason': reason},
                    'is_general': True,
                    'confidence_tier': 'low',
                    'needs_clarification': False
                }
        
        # Create virtual General service with default charge
        logger.debug(f"Creating virtual General Service (reason: {reason})")
        return {
            'service': {
                'id': 'general_default',
                'name': 'General Callout',
                'category': 'General',
                'description': 'Default callout service',
                'duration_minutes': default_duration,
                'price': default_charge,
                'emergency_price': default_charge * 1.5  # 50% more for emergency
            },
            'score': 0,
            'matched_name': 'General Callout (default)',
            'match_details': {'type': 'virtual_fallback', 'reason': reason},
            'is_general': True,
            'confidence_tier': 'low',
            'needs_clarification': False
        }


class AIServiceMatcher:
    """
    AI-powered service matching using OpenAI for complex descriptions.
    
    Use this when:
    - Fuzzy matching returns low confidence (General Service fallback)
    - Customer asks for price/duration information
    
    Performance: ~200-400ms per call (only used as fallback)
    """
    
    # Simple in-memory cache for repeated queries (cleared on restart)
    _cache = {}
    _cache_max_size = 100
    
    @classmethod
    def _get_cache_key(cls, job_description: str, services: list) -> str:
        """Generate cache key from job description and service names"""
        service_names = tuple(sorted(s.get('name', '') for s in services))
        return f"{job_description.lower().strip()}:{hash(service_names)}"
    
    @classmethod
    def match(cls, job_description: str, services: list, default_duration: int = 1440) -> dict:
        """
        Match a job description to the best service using AI.
        
        Args:
            job_description: Description of the job from customer
            services: List of service dicts from database
            default_duration: Default duration if no match found (1 day for trades)
            
        Returns:
            Dict with matched service info
        """
        if not job_description or not job_description.strip():
            return ServiceMatcher._create_general_fallback(services, default_duration, "empty_description")
        
        if not services:
            return ServiceMatcher._create_general_fallback(services, default_duration, "no_services")
        
        # Filter out General Service from matching candidates
        matching_services = [s for s in services if 'general' not in (s.get('name') or '').lower()]
        if not matching_services:
            return ServiceMatcher._create_general_fallback(services, default_duration, "only_general_service")
        
        # Check cache first
        cache_key = cls._get_cache_key(job_description, matching_services)
        if cache_key in cls._cache:
            logger.debug(f"AI match cache hit for: '{job_description[:50]}...'")
            return cls._cache[cache_key]
        
        try:
            import time as time_module
            ai_match_start = time_module.time()
            
            from openai import OpenAI
            from src.utils.config import config
            import json
            
            client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=5.0)  # 5 second timeout
            
            # Build compact service list for the prompt
            service_list = []
            for i, svc in enumerate(matching_services):
                name = svc.get('name', 'Unknown')
                desc = svc.get('description', '')
                # Keep descriptions short to reduce tokens
                if desc and len(desc) > 50:
                    desc = desc[:50] + '...'
                service_list.append(f"{i+1}. {name}" + (f" ({desc})" if desc else ""))
            
            services_text = "\n".join(service_list)
            
            response = client.chat.completions.create(
                model=config.CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Match customer problem to service. Return JSON: {\"idx\":<1-based index or 0 if no match>,\"conf\":<0-100>}"
                    },
                    {
                        "role": "user",
                        "content": f"Problem: {job_description[:200]}\n\nServices:\n{services_text}"
                    }
                ],
                temperature=0,
                **config.max_tokens_param(value=50)
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response - handle markdown code blocks
            if '```' in result_text:
                result_text = result_text.split('```')[1].replace('json', '').strip()
            
            result = json.loads(result_text)
            service_index = result.get('idx', result.get('service_index', 0))
            confidence = result.get('conf', result.get('confidence', 0))
            
            ai_match_duration = time_module.time() - ai_match_start
            print(f"[SERVICE_TIMING] ⏱️ AI service match took {ai_match_duration:.3f}s")
            
            # Valid match found
            if service_index > 0 and service_index <= len(matching_services) and confidence >= 40:
                matched_service = matching_services[service_index - 1]
                logger.info(f"AI match: '{job_description[:30]}...' -> '{matched_service.get('name')}' ({confidence}%)")
                
                match_result = {
                    'service': matched_service,
                    'score': confidence,
                    'matched_name': matched_service.get('name', 'Unknown'),
                    'match_details': {'type': 'ai_match'},
                    'is_general': False
                }
                
                # Cache the result (with size limit)
                if len(cls._cache) >= cls._cache_max_size:
                    cls._cache.pop(next(iter(cls._cache)))  # Remove oldest
                cls._cache[cache_key] = match_result
                
                return match_result
            
            # No good match
            logger.debug(f"AI match: No match for '{job_description[:30]}...' (conf: {confidence})")
            return ServiceMatcher._create_general_fallback(services, default_duration, f"ai_low_conf:{confidence}")
            
        except Exception as e:
            ai_match_duration = time_module.time() - ai_match_start
            print(f"[SERVICE_TIMING] ❌ AI service match FAILED after {ai_match_duration:.3f}s: {e}")
            logger.warning(f"AI matching failed: {e}")
            return ServiceMatcher._create_general_fallback(services, default_duration, f"ai_error")


def lookup_service_by_name(service_name: str, company_id: int = None) -> dict:
    """
    Look up a service by name, preferring exact matches but tolerating slight variations.
    
    Used by tool handlers (book_job, get_next_available, etc.) where the service was
    already confirmed with the caller — we trust the name and just need to resolve
    it to a service record for duration/price/metadata.
    
    Searches all services (including package_only) and packages.
    Prefers standalone services over packages when names are equally close.
    Falls back to match_service() only if nothing scores well.
    """
    from src.services.settings_manager import get_settings_manager
    from difflib import SequenceMatcher
    
    if not service_name or not service_name.strip():
        return match_service(service_name, company_id=company_id)
    
    query = service_name.strip().lower()
    settings_mgr = get_settings_manager()
    all_services = settings_mgr.get_services(company_id=company_id)
    all_packages = settings_mgr.get_packages(company_id=company_id)
    
    # Build candidates: all services (including package_only) + packages
    candidates = []
    
    for svc in all_services:
        svc_name = (svc.get('name') or '').strip().lower()
        if not svc_name or 'general' in svc_name:
            continue  # Skip general services — handled by short-circuit in match_service
        candidates.append({
            'name_lower': svc_name,
            'record': svc,
            'type': 'service',
            'is_general': False,
        })
    
    for pkg in all_packages:
        pkg_name = (pkg.get('name') or '').strip().lower()
        if not pkg_name:
            continue
        pkg_services = pkg.get('services', [])
        duration = pkg.get('duration_override') or pkg.get('total_duration_minutes') or sum(s.get('duration_minutes', 0) for s in pkg_services)
        price = pkg.get('price_override') or pkg.get('total_price') or sum(s.get('price', 0) for s in pkg_services)
        candidates.append({
            'name_lower': pkg_name,
            'record': {
                'id': pkg['id'], 'name': pkg['name'],
                'description': pkg.get('description', ''),
                'category': 'Package', 'duration_minutes': duration,
                'price': price, 'is_package': True, '_package_data': pkg
            },
            'type': 'package',
            'is_general': False,
        })
    
    # Score each candidate
    best = None
    best_score = 0
    
    for c in candidates:
        name = c['name_lower']
        
        # Exact match = 100
        if name == query:
            score = 100
        # Query is contained in name or vice versa
        elif query in name:
            # "leak fix" in "leak fix and investigation" → penalize longer names
            score = 95 - (len(name) - len(query))
        elif name in query:
            # "leak fix" contains "leak" → penalize shorter names
            score = 90 - (len(query) - len(name))
        else:
            # Fuzzy similarity
            score = int(SequenceMatcher(None, query, name).ratio() * 85)
        
        # Tie-breaker: prefer standalone services over packages
        if c['type'] == 'service':
            score += 0.5  # Tiny boost so services win ties
        
        if score > best_score:
            best_score = score
            best = c
    
    # Accept if score is reasonable (>= 70)
    if best and best_score >= 70:
        record = best['record']
        matched_name = record.get('name', service_name)
        match_type = 'exact_lookup' if best_score >= 99 else 'name_lookup'
        
        print(f"[LOOKUP_SERVICE] ✅ {match_type} (score={best_score:.0f}): '{service_name}' -> {best['type']} '{matched_name}'")
        
        result = {
            'service': record,
            'score': int(best_score),
            'matched_name': matched_name,
            'match_details': {'type': match_type},
            'is_general': best['is_general'],
        }
        if best['type'] == 'package':
            result['is_package'] = True
        return result
    
    # Also check General Callout/Service explicitly
    # Prefer General Callout over General Quote when query mentions "callout"
    general_services = []
    for svc in all_services:
        svc_name = (svc.get('name') or '').strip().lower()
        if 'general' in svc_name:
            if query in svc_name or svc_name in query or 'general' in query:
                general_services.append(svc)
    
    if general_services:
        # If query mentions "callout", prefer General Callout; otherwise take first match
        best_general = general_services[0]
        if 'callout' in query:
            for svc in general_services:
                if 'callout' in (svc.get('name') or '').lower():
                    best_general = svc
                    break
        elif 'quote' in query:
            for svc in general_services:
                if 'quote' in (svc.get('name') or '').lower():
                    best_general = svc
                    break
        else:
            # Default: prefer General Callout over General Quote for generic "general" queries
            for svc in general_services:
                if 'callout' in (svc.get('name') or '').lower():
                    best_general = svc
                    break
        
        print(f"[LOOKUP_SERVICE] ✅ General service match: '{service_name}' -> '{best_general.get('name')}'")
        return {
            'service': best_general,
            'score': 90,
            'matched_name': best_general.get('name', 'General Callout'),
            'match_details': {'type': 'general_lookup'},
            'is_general': True,
        }
    
    # Nothing matched well — fall back to full match_service
    print(f"[LOOKUP_SERVICE] ⚠️ No good match for '{service_name}' (best={best_score:.0f}) — falling back to match_service")
    return match_service(service_name, company_id=company_id)


def match_service(job_description: str, company_id: int = None, use_ai_fallback: bool = True) -> dict:
    """
    Match a job description to a service from the services menu.
    
    Uses intelligent multi-strategy matching that works with any services.
    Falls back to AI matching if fuzzy match confidence is low.
    Falls back to "General Service" if no good match is found.
    
    Args:
        job_description: Description of the job (e.g., 'leaking pipe', 'power outage')
        company_id: Company ID for multi-tenant isolation
        use_ai_fallback: Whether to use AI matching when fuzzy match is low confidence (default True)
    
    Returns:
        Dict with matched service info:
        {
            'service': The matched service dict (or General service),
            'score': Match score (0-100),
            'matched_name': Name of matched service,
            'is_general': True if fell back to General service
        }
    """
    from src.services.settings_manager import get_settings_manager
    
    try:
        # Load services and packages from database
        settings_mgr = get_settings_manager()
        services = settings_mgr.get_services(company_id=company_id)
        packages = settings_mgr.get_packages(company_id=company_id)
        default_duration = settings_mgr.get_default_duration_minutes(company_id=company_id)
        
        # Filter package_only services from standalone pool
        standalone_services = [s for s in services if not s.get('package_only', False)]
        
        # Short-circuit: if explicitly requesting General Callout/Service, return it directly
        # This prevents other matchers from overriding an intentional general booking
        desc_lower = (job_description or '').strip().lower()
        if desc_lower in ('general callout', 'general service', 'general') or desc_lower.startswith('general callout') or desc_lower.startswith('general service'):
            logger.info(f"[MATCH_SERVICE] Short-circuit: explicit general request '{job_description}'")
            print(f"[MATCH_SERVICE] ⚡ Short-circuit to General Callout for '{job_description}'")
            return ServiceMatcher._create_general_fallback(standalone_services, default_duration, "explicit_general_request")
        
        # First try fast fuzzy matching with packages
        result = ServiceMatcher.match(job_description, standalone_services, default_duration, packages=packages)
        
        # If fuzzy match has low confidence and we have multiple services, try AI matching
        # AI threshold: score < 50 means fuzzy match isn't confident
        if use_ai_fallback and result.get('is_general', False) and len(standalone_services) > 1:
            logger.debug(f"Fuzzy match returned General Service (score: {result.get('score', 0)}) - trying AI matching")
            try:
                ai_result = AIServiceMatcher.match(job_description, standalone_services, default_duration)
                # Only use AI result if it found a specific service (not General)
                if not ai_result.get('is_general', True):
                    logger.info(f"AI match improved result: '{job_description}' -> '{ai_result['matched_name']}' (confidence: {ai_result.get('score', 0)})")
                    # Tag package results from AI matcher
                    if ai_result.get('service', {}).get('is_package'):
                        ai_result['is_package'] = True
                    return ai_result
            except Exception as ai_error:
                logger.warning(f"AI matching failed, using fuzzy result: {ai_error}")
        
        return result
        
    except Exception as e:
        logger.warning(f"Error matching service: {e}")
        from src.utils.config import config
        default_charge = getattr(config, 'DEFAULT_APPOINTMENT_CHARGE', 50.0)
        return {
            'service': {
                'id': 'general_default',
                'name': 'General Callout',
                'category': 'General',
                'description': 'Default callout service',
                'duration_minutes': 60,
                'price': default_charge,
                'emergency_price': default_charge * 1.5
            },
            'score': 0,
            'matched_name': 'General Callout (error fallback)',
            'match_details': {'type': 'error', 'error': str(e)},
            'is_general': True
        }


def get_service_price(job_description: str, urgency: str = 'scheduled', company_id: int = None) -> float:
    """
    Get the price for a service from the services menu based on job description and urgency.
    
    Uses the unified match_service function for consistent matching.
    
    Args:
        job_description: Description of the job (e.g., 'exterior painting', 'leak repairs')
        urgency: Urgency level ('emergency', 'same-day', 'scheduled', 'quote')
        company_id: Company ID for multi-tenant isolation
    
    Returns:
        Price in EUR, or 0 as default if not found
    """
    try:
        match_result = match_service(job_description, company_id=company_id)
        service = match_result['service']
        
        # Use emergency price if urgency is emergency and available
        if urgency == 'emergency' and service.get('emergency_price'):
            price = float(service['emergency_price'])
            logger.debug(f"Pricing: '{job_description}' -> '{match_result['matched_name']}' - EMERGENCY: EUR{price}")
            return price
        else:
            price = float(service.get('price', 0))
            logger.debug(f"Pricing: '{job_description}' -> '{match_result['matched_name']}' - Standard: EUR{price}")
            return price
        
    except Exception as e:
        logger.warning(f"Error loading service price: {e}, using default EUR0")
        return 0


def match_service_with_ai(job_description: str, company_id: int = None, use_ai: bool = True) -> dict:
    """
    Match a job description to a service, optionally using AI for better accuracy.
    
    Use this when:
    - Customer asks about price or duration
    - Call ends and we need accurate service categorization
    - Fuzzy matching returns low confidence
    
    Args:
        job_description: Description of the job
        company_id: Company ID for multi-tenant isolation
        use_ai: Whether to use AI matching (default True)
    
    Returns:
        Dict with matched service info
    """
    from src.services.settings_manager import get_settings_manager
    
    try:
        settings_mgr = get_settings_manager()
        services = settings_mgr.get_services(company_id=company_id)
        default_duration = settings_mgr.get_default_duration_minutes(company_id=company_id)
        
        if use_ai and len(services) > 1:
            # Use AI matching for better accuracy
            return AIServiceMatcher.match(job_description, services, default_duration)
        else:
            # Use fast fuzzy matching
            return ServiceMatcher.match(job_description, services, default_duration)
            
    except Exception as e:
        logger.warning(f"Error in AI service matching: {e}")
        return match_service(job_description, company_id=company_id)


def get_service_info_with_ai(job_description: str, company_id: int = None) -> dict:
    """
    Get comprehensive service info using AI matching.
    
    Use this when customer asks about price, duration, or service details.
    Returns price, duration, and service name in one call.
    
    Args:
        job_description: Description of the job
        company_id: Company ID for multi-tenant isolation
    
    Returns:
        Dict with service info: {
            'service_name': str,
            'price': float,
            'duration_minutes': int,
            'is_general': bool,
            'confidence': int
        }
    """
    match_result = match_service_with_ai(job_description, company_id=company_id, use_ai=True)
    service = match_result['service']
    
    return {
        'service_name': match_result['matched_name'],
        'price': float(service.get('price', 0)),
        'duration_minutes': int(service.get('duration_minutes', 60)),
        'is_general': match_result.get('is_general', False),
        'confidence': match_result.get('score', 0)
    }


def get_service_duration(job_description: str, company_id: int = None) -> int:
    """
    Get the duration for a service from the services menu based on job description.
    
    Uses the unified match_service function for consistent matching.
    
    Args:
        job_description: Description of the job (e.g., 'exterior painting', 'leak repairs')
        company_id: Company ID for multi-tenant isolation
    
    Returns:
        Duration in minutes, or default duration if not found
    """
    try:
        from src.services.settings_manager import get_settings_manager
        settings_mgr = get_settings_manager()
        default_duration = settings_mgr.get_default_duration_minutes(company_id=company_id)
        
        match_result = match_service(job_description, company_id=company_id)
        service = match_result['service']
        
        duration = service.get('duration_minutes', default_duration)
        logger.debug(f"Duration: '{job_description}' -> '{match_result['matched_name']}' - {duration} mins")
        return duration
        
    except Exception as e:
        logger.warning(f"Error loading service duration: {e}, using default 1440 mins (1 day)")
        return 1440


def get_matched_service_name(job_description: str, company_id: int = None) -> str:
    """
    Get the matched service name for a job description.
    
    Args:
        job_description: Description of the job
        company_id: Company ID for multi-tenant isolation
    
    Returns:
        Name of the matched service
    """
    match_result = match_service(job_description, company_id=company_id)
    return match_result['matched_name']


def _resolve_callout_duration(matched_service: dict, company_id: int = None) -> int:
    """If a service requires an initial callout, return the General Callout duration instead."""
    if not matched_service.get('requires_callout'):
        return matched_service.get('duration_minutes', 60)
    
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    all_services = settings_mgr.get_services(company_id=company_id)
    for svc in all_services:
        svc_name = (svc.get('name') or '').lower()
        if 'general callout' in svc_name or ('general' in svc_name and 'callout' in svc_name):
            return svc.get('duration_minutes', 60)
    for svc in all_services:
        if 'callout' in (svc.get('name') or '').lower():
            return svc.get('duration_minutes', 60)
    return 60  # Default callout duration


def _resolve_quote_duration(matched_service: dict, company_id: int = None) -> int:
    """If a service requires an initial quote, return the General Quote duration instead."""
    if not matched_service.get('requires_quote'):
        return matched_service.get('duration_minutes', 60)
    
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    all_services = settings_mgr.get_services(company_id=company_id)
    for svc in all_services:
        svc_name = (svc.get('name') or '').lower()
        if 'general quote' in svc_name or ('general' in svc_name and 'quote' in svc_name):
            return svc.get('duration_minutes', 240)
    for svc in all_services:
        if 'quote' in (svc.get('name') or '').lower():
            return svc.get('duration_minutes', 240)
    return 240  # Default quote duration (4 hours)

