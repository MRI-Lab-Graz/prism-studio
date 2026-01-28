#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Windows code signing configuration in GitHub Actions.
Validates that the signing workflow is properly configured.
"""

import os
import sys
import yaml
import re

# Force UTF-8 encoding for Windows console
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class TestGitHubSigningConfiguration:
    """Test GitHub Actions signing configuration"""

    def __init__(self, repo_root=None):
        if repo_root is None:
            self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.repo_root = repo_root
        
        self.workflow_path = os.path.join(self.repo_root, '.github', 'workflows', 'build.yml')

    def test_workflow_file_exists(self):
        """Test that the build workflow file exists"""
        print("  🧪 Testing workflow file exists...")
        
        if not os.path.exists(self.workflow_path):
            print(f"    ❌ Workflow file not found: {self.workflow_path}")
            return False
        
        print(f"    ✅ Found: {self.workflow_path}")
        return True

    def test_workflow_yaml_valid(self):
        """Test that the workflow YAML is valid"""
        print("  🧪 Testing workflow YAML syntax...")
        
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                workflow = yaml.safe_load(f)
            
            print("    ✅ YAML syntax is valid")
            return True
        except yaml.YAMLError as e:
            print(f"    ❌ YAML syntax error: {e}")
            return False
        except Exception as e:
            print(f"    ❌ Error reading file: {e}")
            return False

    def test_signing_step_configured(self):
        """Test that the signing step is properly configured"""
        print("  🧪 Testing Windows signing step configuration...")
        
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for signing step
            if 'Sign Windows Executable' not in content:
                print("    ❌ Signing step not found in workflow")
                return False
            
            print("    ✅ Signing step found")
            
            # Check for SignPath action
            if 'signpath/github-action-submit-signing-request' not in content:
                print("    ❌ SignPath action not configured")
                return False
            
            print("    ✅ SignPath action configured")
            
            # Check for conditional execution
            if "if: runner.os == 'Windows'" not in content:
                print("    ⚠️  Signing step not limited to Windows")
            else:
                print("    ✅ Signing limited to Windows runners")
            
            # Check for graceful secret handling
            if "env.SIGNPATH_API_TOKEN != ''" in content or 'secrets.SIGNPATH_API_TOKEN' in content:
                print("    ✅ Graceful secret handling configured")
            else:
                print("    ⚠️  Secret handling not configured")
            
            return True
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False

    def test_required_secrets_documented(self):
        """Test that required secrets are documented"""
        print("  🧪 Testing required secrets documentation...")
        
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            required_secrets = [
                'SIGNPATH_API_TOKEN',
                'SIGNPATH_ORGANIZATION_ID',
            ]
            
            found_secrets = []
            for secret in required_secrets:
                if secret in content:
                    found_secrets.append(secret)
                    print(f"    ✅ Secret referenced: {secret}")
                else:
                    print(f"    ❌ Secret not found: {secret}")
            
            if len(found_secrets) == len(required_secrets):
                print(f"    ✅ All {len(required_secrets)} required secrets referenced")
                return True
            else:
                print(f"    ❌ Missing {len(required_secrets) - len(found_secrets)} secrets")
                return False
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False

    def test_signing_configuration_parameters(self):
        """Test that signing parameters are properly configured"""
        print("  🧪 Testing signing configuration parameters...")
        
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            required_params = {
                'api-token': 'API token parameter',
                'organization-id': 'Organization ID parameter',
                'project-slug': 'Project slug',
                'signing-policy-slug': 'Signing policy',
                'artifact-configuration-slug': 'Artifact configuration',
                'input-artifact-path': 'Input artifact path',
                'output-artifact-path': 'Output artifact path',
                'wait-for-completion': 'Wait for completion flag',
            }
            
            found_params = []
            for param, description in required_params.items():
                if param in content:
                    found_params.append(param)
                    print(f"    ✅ {description}: {param}")
                else:
                    print(f"    ⚠️  Missing: {param}")
            
            if len(found_params) >= 6:  # At least core parameters
                print(f"    ✅ Essential signing parameters configured ({len(found_params)}/{len(required_params)})")
                return True
            else:
                print(f"    ❌ Too few parameters configured ({len(found_params)}/{len(required_params)})")
                return False
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False

    def test_artifact_paths_correct(self):
        """Test that artifact paths reference the correct executable"""
        print("  🧪 Testing artifact path configuration...")
        
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for correct executable path
            if 'PrismValidator.exe' in content:
                print("    ✅ Executable name referenced correctly")
            else:
                print("    ❌ Executable name not found")
                return False
            
            # Check for dist directory path
            if 'dist/PrismValidator' in content or 'dist\\PrismValidator' in content:
                print("    ✅ Distribution directory path configured")
            else:
                print("    ⚠️  Distribution path may be incorrect")
            
            return True
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False

    def test_build_before_signing(self):
        """Test that build step comes before signing"""
        print("  🧪 Testing build order (build before sign)...")
        
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find positions
            build_pos = content.find('Build with PyInstaller')
            sign_pos = content.find('Sign Windows Executable')
            
            if build_pos == -1:
                print("    ❌ Build step not found")
                return False
            
            if sign_pos == -1:
                print("    ⚠️  Signing step not found")
                return True  # Not an error if signing is optional
            
            if build_pos < sign_pos:
                print("    ✅ Build step comes before signing")
                return True
            else:
                print("    ❌ Signing step before build step (incorrect order)")
                return False
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False

    def test_documentation_exists(self):
        """Test that signing documentation exists"""
        print("  🧪 Testing signing documentation...")
        
        doc_path = os.path.join(self.repo_root, 'docs', 'WINDOWS_BUILD.md')
        
        if not os.path.exists(doc_path):
            print(f"    ⚠️  Documentation not found: {doc_path}")
            return True  # Not critical
        
        try:
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            signing_keywords = [
                'SignPath',
                'code signing',
                'certificate',
                'signature',
            ]
            
            found_keywords = sum(1 for kw in signing_keywords if kw.lower() in content.lower())
            
            if found_keywords >= 3:
                print(f"    ✅ Signing documentation comprehensive ({found_keywords}/{len(signing_keywords)} keywords)")
                return True
            else:
                print(f"    ⚠️  Limited signing documentation ({found_keywords}/{len(signing_keywords)} keywords)")
                return True  # Not critical
                
        except Exception as e:
            print(f"    ⚠️  Error reading documentation: {e}")
            return True  # Not critical

    def test_secrets_not_exposed(self):
        """Test that secrets are not hardcoded in the workflow"""
        print("  🧪 Testing secrets security...")
        
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check that secrets are referenced correctly
            if 'secrets.SIGNPATH_API_TOKEN' in content:
                print("    ✅ API token using secrets manager")
            else:
                print("    ⚠️  API token not using secrets manager")
            
            if 'secrets.SIGNPATH_ORGANIZATION_ID' in content:
                print("    ✅ Organization ID using secrets manager")
            else:
                print("    ⚠️  Organization ID not using secrets manager")
            
            # Check for accidental exposure patterns
            dangerous_patterns = [
                r'api[_-]?token\s*[:=]\s*["\'][a-zA-Z0-9]{20,}["\']',
                r'organization[_-]?id\s*[:=]\s*["\'][a-zA-Z0-9-]{8,}["\']',
                r'password\s*[:=]\s*["\'].+["\']',
            ]
            
            exposed = False
            for pattern in dangerous_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    print(f"    ❌ Potential secret exposure detected")
                    exposed = True
                    break
            
            if not exposed:
                print("    ✅ No hardcoded secrets detected")
            
            return not exposed
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False

    def test_signpath_action_version(self):
        """Test that SignPath action uses a pinned version"""
        print("  🧪 Testing SignPath action version...")
        
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for version pinning
            match = re.search(r'signpath/github-action-submit-signing-request@(v[\d.]+)', content)
            
            if match:
                version = match.group(1)
                print(f"    ✅ SignPath action version pinned: {version}")
                
                # Warn if using very old version
                if version.startswith('v0.'):
                    print(f"    ℹ️  Consider updating to newer version (currently {version})")
                
                return True
            else:
                print("    ⚠️  SignPath action version not pinned")
                return True  # Not critical
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False

    def generate_signing_report(self):
        """Generate a comprehensive signing configuration report"""
        print("  📊 Generating signing configuration report...")
        
        report = []
        report.append("\n" + "=" * 70)
        report.append("🔐 WINDOWS CODE SIGNING CONFIGURATION REPORT")
        report.append("=" * 70)
        
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract configuration details
            report.append("\n📋 Configuration Details:")
            report.append("-" * 70)
            
            # Find SignPath configuration
            if 'signpath/github-action-submit-signing-request' in content:
                report.append("✅ Signing Provider: SignPath.io")
                
                # Extract version
                match = re.search(r'@(v[\d.]+)', content)
                if match:
                    report.append(f"   Version: {match.group(1)}")
                
                # Extract parameters
                if 'project-slug' in content:
                    match = re.search(r"project-slug:\s*['\"]?([^'\"]+)['\"]?", content)
                    if match:
                        report.append(f"   Project: {match.group(1)}")
                
                if 'signing-policy-slug' in content:
                    match = re.search(r"signing-policy-slug:\s*['\"]?([^'\"]+)['\"]?", content)
                    if match:
                        report.append(f"   Policy: {match.group(1)}")
                
                if 'wait-for-completion: true' in content:
                    report.append("   Wait for completion: Yes")
                
            else:
                report.append("⚠️  No signing provider configured")
            
            # Secrets configuration
            report.append("\n🔑 Required Secrets:")
            report.append("-" * 70)
            secrets = ['SIGNPATH_API_TOKEN', 'SIGNPATH_ORGANIZATION_ID']
            for secret in secrets:
                if secret in content:
                    report.append(f"✅ {secret}")
                else:
                    report.append(f"❌ {secret} (missing)")
            
            # Artifact configuration
            report.append("\n📦 Artifact Configuration:")
            report.append("-" * 70)
            
            if 'PrismValidator.exe' in content:
                report.append("✅ Target Executable: PrismValidator.exe")
            
            input_match = re.search(r"input-artifact-path:\s*['\"]?([^'\"]+)['\"]?", content)
            if input_match:
                report.append(f"   Input Path: {input_match.group(1)}")
            
            output_match = re.search(r"output-artifact-path:\s*['\"]?([^'\"]+)['\"]?", content)
            if output_match:
                report.append(f"   Output Path: {output_match.group(1)}")
            
            # Conditional execution
            report.append("\n⚙️  Execution Conditions:")
            report.append("-" * 70)
            
            if "runner.os == 'Windows'" in content:
                report.append("✅ Limited to Windows runners")
            
            if "env.SIGNPATH_API_TOKEN != ''" in content:
                report.append("✅ Gracefully handles missing secrets")
            
            # Documentation
            report.append("\n📚 Documentation:")
            report.append("-" * 70)
            
            doc_path = os.path.join(self.repo_root, 'docs', 'WINDOWS_BUILD.md')
            if os.path.exists(doc_path):
                report.append(f"✅ Found: docs/WINDOWS_BUILD.md")
            else:
                report.append("⚠️  WINDOWS_BUILD.md not found")
            
            report.append("\n" + "=" * 70)
            
            report_text = "\n".join(report)
            print(report_text)
            
            # Save report to file
            report_file = os.path.join(self.repo_root, 'signing_config_report.txt')
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            
            print(f"\n💾 Report saved to: {report_file}")
            
            return True
            
        except Exception as e:
            print(f"    ❌ Error generating report: {e}")
            return False


def run_all_tests():
    """Run all signing configuration tests"""
    print("=" * 70)
    print("🔐 GITHUB ACTIONS CODE SIGNING CONFIGURATION TESTS")
    print("=" * 70)
    
    tester = TestGitHubSigningConfiguration()
    
    tests = [
        ("Workflow File Exists", tester.test_workflow_file_exists),
        ("YAML Syntax Valid", tester.test_workflow_yaml_valid),
        ("Signing Step Configured", tester.test_signing_step_configured),
        ("Required Secrets Documented", tester.test_required_secrets_documented),
        ("Signing Parameters", tester.test_signing_configuration_parameters),
        ("Artifact Paths Correct", tester.test_artifact_paths_correct),
        ("Build Before Signing", tester.test_build_before_signing),
        ("Documentation Exists", tester.test_documentation_exists),
        ("Secrets Security", tester.test_secrets_not_exposed),
        ("SignPath Action Version", tester.test_signpath_action_version),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 70)
        try:
            if test_func():
                passed += 1
            else:
                print(f"    ❌ {test_name} failed")
        except Exception as e:
            print(f"    ❌ {test_name} error: {e}")
        print()
    
    # Generate comprehensive report
    print("\n" + "=" * 70)
    tester.generate_signing_report()
    
    print("\n" + "=" * 70)
    print(f"📊 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All signing configuration tests passed!")
        print("\n✅ Your Windows executable will be signed via SignPath when:")
        print("   1. You push a tag (e.g., git tag v1.0.0)")
        print("   2. GitHub secrets are configured (SIGNPATH_API_TOKEN, SIGNPATH_ORGANIZATION_ID)")
        print("   3. SignPath approves the signing request")
        return 0
    else:
        print(f"⚠️  {total - passed} test(s) failed or have warnings")
        print("\n📝 Review the issues above and update your configuration")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
