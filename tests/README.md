```bash
# Script Testing
pytest tests/test_auth.py
# Method Testing
pytest tests/test_auth.py::test_sgimed_integration_for_existing_user
# Coverage Testing
pytest --cov=. --cov-report html tests/test_auth.py 
```