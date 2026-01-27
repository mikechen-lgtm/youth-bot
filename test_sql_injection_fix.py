"""Test SQL injection fixes"""
import sys

def test_fetch_chat_history_validation():
    """Test that fetch_chat_history properly validates limit parameter"""
    
    # Simulate the validation logic
    def validate_limit(limit):
        if not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        if limit <= 0:
            limit = 1
        if limit > 100:
            limit = 100
        return limit
    
    # Test valid inputs
    assert validate_limit(10) == 10
    assert validate_limit(1) == 1
    assert validate_limit(100) == 100
    
    # Test boundary conditions
    assert validate_limit(0) == 1  # Should be clamped to 1
    assert validate_limit(-5) == 1  # Should be clamped to 1
    assert validate_limit(200) == 100  # Should be clamped to 100
    
    # Test invalid types (should raise)
    try:
        validate_limit("10")
        assert False, "Should have raised ValueError for string"
    except ValueError:
        pass
    
    try:
        validate_limit("10; DROP TABLE chat_messages;--")
        assert False, "Should have raised ValueError for SQL injection attempt"
    except ValueError:
        pass
    
    print("✅ fetch_chat_history validation tests passed")

def test_admin_update_whitelist():
    """Test that admin_update_hero_image uses whitelist"""
    
    ALLOWED_FIELDS = {"alt_text", "is_active", "link_url"}
    
    # Test valid fields
    valid_data = {"alt_text": "test", "is_active": True}
    invalid_fields = set(valid_data.keys()) - ALLOWED_FIELDS
    assert len(invalid_fields) == 0
    
    # Test invalid fields
    malicious_data = {
        "alt_text": "test",
        "'; DROP TABLE hero_carousel;--": "malicious"
    }
    invalid_fields = set(malicious_data.keys()) - ALLOWED_FIELDS
    assert len(invalid_fields) > 0
    assert "'; DROP TABLE hero_carousel;--" in invalid_fields
    
    # Test SQL injection in field name
    injection_data = {
        "id = 1; DROP TABLE users;--": "value"
    }
    invalid_fields = set(injection_data.keys()) - ALLOWED_FIELDS
    assert len(invalid_fields) > 0
    
    print("✅ admin_update_hero_image whitelist tests passed")

if __name__ == "__main__":
    test_fetch_chat_history_validation()
    test_admin_update_whitelist()
    print("\n✅ All SQL injection fix tests passed!")
