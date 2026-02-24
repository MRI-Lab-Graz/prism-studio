# Contributing to PRISM

Thank you for considering contributing to PRISM! We welcome contributions of all kinds, including bug reports, feature requests, documentation improvements, and code contributions.

## License Agreement

By contributing, you agree that your contributions will be licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). If you are an organization or otherwise cannot agree to this, please contact us before contributing.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue on GitHub with:
- A clear, descriptive title
- Steps to reproduce the issue
- Expected vs. actual behavior
- Your environment (OS, Python version, PRISM version)
- Sample data or minimal example (if applicable)

### Suggesting Features

Feature requests are welcome! Please open an issue with:
- A clear description of the feature
- Use cases and motivation
- Example workflows or mockups (if applicable)

### Contributing Code

1. **Fork the repository** and clone your fork locally
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Set up your development environment**:
   ```bash
   bash setup.sh  # macOS/Linux
   # OR
   .\setup.ps1    # Windows
   ```
4. **Make your changes** following our coding standards (see below)
5. **Run tests** to ensure nothing breaks:
   ```bash
   ./run_tests.sh  # macOS/Linux
   # OR
   python run_all_tests.py
   ```
6. **Commit your changes** with clear, descriptive commit messages
7. **Push to your fork** and **open a pull request** against `main`

### Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Ensure all tests pass
- Update documentation if needed
- Add tests for new functionality

## Coding Standards

- Follow PEP 8 style guidelines for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and modular
- Use type hints where appropriate

## Testing

We maintain comprehensive test coverage. When adding new features:
- Add unit tests in `tests/test_unit.py` for isolated functionality
- Add integration tests in `tests/test_validator.py` for validation logic
- Add web tests in `tests/test_web_*.py` for web interface features
- Ensure cross-platform compatibility (test on Windows if possible)

## Documentation

Documentation is in the `docs/` folder and built with Sphinx:
- Update relevant `.md` files when changing functionality
- Add examples for new features
- Keep screenshots and examples up to date
- Use clear, concise language

## Community

- Be respectful and constructive in discussions
- Help others learn and grow
- Follow the code of conduct (implied: be professional and inclusive)

## Questions?

If you have questions about contributing, feel free to:
- Open a discussion on GitHub
- Contact the maintainer(s)
- Check the documentation at https://prism-studio.readthedocs.io

Thank you for helping make PRISM better!
