#!/usr/bin/env python3
"""
FAIR Compliance Checker for Psycho-Validator
Evaluates datasets against FAIR principles and provides recommendations
"""

import json
import os
import re
from pathlib import Path

class FAIRComplianceChecker:
    def __init__(self):
        self.score = {
            'findable': 0,
            'accessible': 0, 
            'interoperable': 0,
            'reusable': 0
        }
        self.max_scores = {
            'findable': 25,
            'accessible': 25,
            'interoperable': 25, 
            'reusable': 25
        }
        self.recommendations = []
    
    def check_findable(self, metadata):
        """Check Findable criteria (supports both dataset and stimulus metadata)"""
        score = 0
        
        # Detect metadata type
        is_dataset = "BIDSVersion" in metadata
        
        # F1: Unique identifier
        if is_dataset:
            doi = metadata.get('DatasetDOI')
        else:
            doi = metadata.get('Metadata', {}).get('DatasetDOI')
            
        if doi and doi != "10.PLACEHOLDER/dataset-doi":
            score += 7
            self.recommendations.append("✅ Dataset has valid DOI for unique identification")
        elif doi:
            score += 3
            self.recommendations.append("⚠️ DOI placeholder found - replace with actual DOI")
        else:
            self.recommendations.append("❌ Add DOI for unique dataset identification")
        
        # F2: Rich metadata
        if is_dataset:
            # Dataset-level metadata requirements
            required_fields = {
                'Name': metadata.get('Name'),
                'Description': metadata.get('Description'),
                'Authors': metadata.get('Authors'),
                'Keywords': metadata.get('Keywords')
            }
            
            present_fields = sum(1 for v in required_fields.values() if v)
            score += min(8, present_fields * 2)
            
            missing = [k for k, v in required_fields.items() if not v]
            if missing:
                self.recommendations.append(f"❌ Missing dataset metadata: {', '.join(missing)}")
            else:
                self.recommendations.append("✅ All essential dataset metadata present")
        else:
            # Stimulus-level metadata (backwards compatibility)
            required_fields = ['Creator', 'CreationDate', 'SchemaVersion']
            missing_fields = [f for f in required_fields if not metadata.get('Metadata', {}).get(f)]
            
            if not missing_fields:
                score += 5
                self.recommendations.append("✅ All required metadata fields present")
            else:
                self.recommendations.append(f"❌ Missing required metadata: {', '.join(missing_fields)}")
        
        # F3: Keywords and descriptions
        if is_dataset:
            keywords = metadata.get('Keywords', [])
            description = metadata.get('Description', '')
        else:
            keywords = metadata.get('Metadata', {}).get('Keywords', [])
            description = metadata.get('Metadata', {}).get('Description', '')
            
        if keywords and len(keywords) >= 3:
            score += 5
            self.recommendations.append(f"✅ Good keyword coverage ({len(keywords)} keywords)")
        else:
            self.recommendations.append("❌ Add at least 3 keywords for better discoverability")
        
        if description and len(description) > 50:
            score += 3
            self.recommendations.append("✅ Detailed description provided")
        else:
            self.recommendations.append("❌ Add comprehensive description (>50 characters)")
        
        # F4: ORCID identification
        if is_dataset:
            # Check if any author has ORCID
            authors = metadata.get('Authors', [])
            orcid_count = 0
            for author in authors:
                if isinstance(author, dict) and author.get('orcid'):
                    orcid_count += 1
            
            if orcid_count > 0:
                score += 5
                self.recommendations.append(f"✅ {orcid_count} author(s) have ORCID identifiers")
            else:
                self.recommendations.append("❌ Add ORCID IDs for authors")
        else:
            if metadata.get('Metadata', {}).get('CreatorORCID'):
                score += 5
                self.recommendations.append("✅ Creator has ORCID identifier")
            else:
                self.recommendations.append("❌ Add CreatorORCID for researcher identification")
        
        # F5: Institutional affiliation
        if is_dataset:
            # Check ROR IDs in author affiliations
            ror_count = 0
            authors = metadata.get('Authors', [])
            for author in authors:
                if isinstance(author, dict) and author.get('ror'):
                    ror_count += 1
            
            if ror_count > 0:
                score += 2
                self.recommendations.append(f"✅ {ror_count} institution(s) have ROR identifiers")
            else:
                self.recommendations.append("❌ Add ROR IDs for institutional identification")
        else:
            if metadata.get('Metadata', {}).get('InstitutionROR'):
                score += 5
                self.recommendations.append("✅ Institution has ROR identifier")
            else:
                self.recommendations.append("❌ Add InstitutionROR for institutional identification")
        
        return score
    
    def check_accessible(self, metadata, file_path):
        """Check Accessible criteria (supports both dataset and stimulus metadata)"""
        score = 0
        
        # Detect metadata type
        is_dataset = "BIDSVersion" in metadata
        
        # A1: Clear license
        if is_dataset:
            license_info = metadata.get('License')
        else:
            license_info = metadata.get('Metadata', {}).get('License')
            
        if license_info and license_info != 'All rights reserved':
            score += 8
            if license_info.startswith('CC'):
                self.recommendations.append(f"✅ Open license specified: {license_info}")
            else:
                self.recommendations.append(f"✅ License specified: {license_info}")
        else:
            self.recommendations.append("❌ Specify clear usage license (e.g., CC-BY-4.0, CC0)")
        
        # A2: Standard format and structure
        if is_dataset:
            # Check BIDS compliance
            if metadata.get('BIDSVersion'):
                score += 5
                self.recommendations.append(f"✅ BIDS-compliant structure (v{metadata.get('BIDSVersion')})")
            else:
                self.recommendations.append("❌ Use BIDS-compliant data structure")
        else:
            # Check file format for stimulus data
            file_format = metadata.get('Technical', {}).get('FileFormat', '').lower()
            standard_formats = ['json', 'tsv', 'csv', 'png', 'jpg', 'wav', 'mp3', 'edf']
            
            if file_format in standard_formats:
                score += 5
                self.recommendations.append(f"✅ Using standard format: {file_format}")
            else:
                self.recommendations.append("❌ Consider using more standard file formats")
        
        # A3: File accessibility
        if os.path.exists(file_path):
            score += 4
            self.recommendations.append("✅ Metadata file is accessible")
        else:
            self.recommendations.append("❌ Metadata file not found or not accessible")
        
        # A4: Documentation completeness
        if is_dataset:
            description = metadata.get('Description', '')
            acknowledgements = metadata.get('Acknowledgements', '')
            readme_path = os.path.join(os.path.dirname(file_path), 'README.md')
            
            doc_score = 0
            if description and len(description) > 100:
                doc_score += 3
                self.recommendations.append("✅ Comprehensive dataset description provided")
            else:
                self.recommendations.append("❌ Add detailed dataset description (>100 characters)")
                
            if acknowledgements:
                doc_score += 2
                self.recommendations.append("✅ Acknowledgements included")
                
            if os.path.exists(readme_path):
                doc_score += 3
                self.recommendations.append("✅ README.md documentation found")
            else:
                self.recommendations.append("❌ Add README.md with dataset documentation")
                
            score += min(4, doc_score)
        else:
            description = metadata.get('Metadata', {}).get('Description')
            if description and len(description) > 50:
                score += 4
                self.recommendations.append("✅ Comprehensive description provided")
            else:
                self.recommendations.append("❌ Add detailed description (>50 characters)")
        
        # A5: Contact information
        if is_dataset:
            contact = metadata.get('Contact', {})
            if contact.get('email'):
                score += 4
                self.recommendations.append("✅ Contact information available")
            else:
                # Check if any author has email
                authors = metadata.get('Authors', [])
                has_email = any(isinstance(a, dict) and a.get('email') for a in authors)
                if has_email:
                    score += 3
                    self.recommendations.append("✅ Author contact information available")
                else:
                    self.recommendations.append("❌ Add contact email in Contact section")
        else:
            creator = metadata.get('Metadata', {}).get('Creator')
            if creator and '@' in creator:  # Basic email check
                score += 4
                self.recommendations.append("✅ Contact information available")
            else:
                self.recommendations.append("❌ Include contact information in Creator field")
                
        # A6: Ethics and permissions
        if is_dataset:
            ethics = metadata.get('EthicsApprovals', [])
            if ethics:
                score += 4
                self.recommendations.append(f"✅ Ethics approval documented ({len(ethics)} approval(s))")
            else:
                self.recommendations.append("❌ Document ethics committee approvals if applicable")
        
        return score
    
    def check_interoperable(self, metadata):
        """Check Interoperable criteria (supports both dataset and stimulus metadata)"""
        score = 0
        
        # Detect metadata type
        is_dataset = "BIDSVersion" in metadata
        
        # I1: Schema compliance and versioning
        if is_dataset:
            bids_version = metadata.get('BIDSVersion')
            if bids_version and re.match(r'^\d+\.\d+\.\d+$', bids_version):
                score += 8
                self.recommendations.append(f"✅ BIDS schema version: {bids_version}")
            else:
                self.recommendations.append("❌ Use valid BIDS version format (X.Y.Z)")
                
            # Check for GeneratedBy versioning
            generated_by = metadata.get('GeneratedBy', [])
            if generated_by and any(g.get('Version') for g in generated_by):
                score += 2
                self.recommendations.append("✅ Software versioning documented")
            else:
                self.recommendations.append("❌ Document software versions in GeneratedBy")
        else:
            schema_version = metadata.get('Metadata', {}).get('SchemaVersion')
            if schema_version and re.match(r'^\d+\.\d+\.\d+$', schema_version):
                score += 8
                self.recommendations.append(f"✅ Valid schema version: {schema_version}")
            else:
                self.recommendations.append("❌ Use semantic versioning for schema compliance")
        
        # I2: Controlled vocabulary and standards
        if is_dataset:
            # Check research domains
            domains = metadata.get('ResearchDomains', [])
            if domains and len(domains) >= 1:
                score += 5
                self.recommendations.append(f"✅ Research domains specified ({len(domains)} domains)")
            else:
                self.recommendations.append("❌ Specify ResearchDomains using controlled vocabulary")
                
            # Check data collection standards
            data_collection = metadata.get('DataCollection', {})
            if data_collection and data_collection.get('start_date'):
                score += 3
                self.recommendations.append("✅ Structured data collection metadata")
            else:
                self.recommendations.append("❌ Add structured DataCollection information")
        else:
            categories = metadata.get('Categories', {})
            if categories and len(categories) >= 2:
                score += 5
                self.recommendations.append("✅ Using controlled vocabulary in categories")
            else:
                self.recommendations.append("❌ Use more structured categories for interoperability")
        
        # I3: Standard format compliance
        if is_dataset:
            # Check dataset type compliance
            dataset_type = metadata.get('DatasetType')
            if dataset_type in ['raw', 'derivative']:
                score += 4
                self.recommendations.append(f"✅ Standard dataset type: {dataset_type}")
            else:
                self.recommendations.append("❌ Use standard DatasetType (raw/derivative)")
                
            # Check file structure implications
            name = metadata.get('Name', '')
            if name and len(name) > 3:
                score += 2
                self.recommendations.append("✅ Descriptive dataset name provided")
        else:
            # Check BIDS naming compliance for stimulus files
            study_fields = metadata.get('Study', {})
            bids_compliance = 0
            for field, value in study_fields.items():
                if field in ['Subject', 'Session', 'Run', 'Task'] and isinstance(value, str):
                    if re.match(r'^(sub-\d+|ses-\w+|run-\d+|task-\w+)$', value) or field == 'Task':
                        bids_compliance += 1
            
            if bids_compliance >= 2:
                score += 6
                self.recommendations.append(f"✅ Good BIDS compliance ({bids_compliance} fields)")
            else:
                self.recommendations.append("❌ Improve BIDS naming convention compliance")
        
        # I4: Linked data and cross-references
        if is_dataset:
            publications = metadata.get('Publications', [])
            references = metadata.get('ReferencesAndLinks', [])
            
            link_score = 0
            if publications:
                valid_dois = sum(1 for p in publications if p.get('doi') and p['doi'].startswith('10.'))
                if valid_dois > 0:
                    link_score += 4
                    self.recommendations.append(f"✅ Linked to publications ({valid_dois} DOIs)")
                else:
                    self.recommendations.append("❌ Add valid DOIs to Publications")
                    
            if references and len(references) > 0:
                link_score += 2
                self.recommendations.append(f"✅ External references provided ({len(references)} links)")
            else:
                self.recommendations.append("❌ Add ReferencesAndLinks for context")
                
            score += min(6, link_score)
        else:
            related_pubs = metadata.get('Metadata', {}).get('RelatedPublications', [])
            if related_pubs:
                score += 6
                self.recommendations.append(f"✅ Linked to publications ({len(related_pubs)} DOIs)")
            else:
                self.recommendations.append("❌ Link to related publications via DOI")
        
        return score
    
    def check_reusable(self, metadata):
        """Check Reusable criteria (supports both dataset and stimulus metadata)"""
        score = 0
        
        # Detect metadata type
        is_dataset = "BIDSVersion" in metadata
        
        # R1: Rich provenance and methodology
        if is_dataset:
            # Check data collection methodology
            data_collection = metadata.get('DataCollection', {})
            method_score = 0
            
            if data_collection.get('start_date') and data_collection.get('end_date'):
                method_score += 3
                self.recommendations.append("✅ Data collection timeline documented")
            else:
                self.recommendations.append("❌ Add DataCollection start_date and end_date")
                
            if data_collection.get('location'):
                method_score += 2
                self.recommendations.append("✅ Data collection location specified")
            else:
                self.recommendations.append("❌ Specify DataCollection location")
                
            if data_collection.get('sample_size'):
                method_score += 3
                self.recommendations.append("✅ Sample size documented")
            else:
                self.recommendations.append("❌ Add sample_size to DataCollection")
                
            score += min(8, method_score)
        else:
            # Stimulus-level technical specifications
            technical_fields = metadata.get('Technical', {})
            required_technical = ['StimulusType', 'FileFormat']
            
            if all(field in technical_fields for field in required_technical):
                score += 8
                self.recommendations.append("✅ Complete technical specifications")
            else:
                missing = [f for f in required_technical if f not in technical_fields]
                self.recommendations.append(f"❌ Missing technical fields: {', '.join(missing)}")
        
        # R2: Clear usage license and guidelines
        if is_dataset:
            license_info = metadata.get('License', '')
            # Check for comprehensive licensing
            if license_info and license_info.startswith('CC'):
                if 'BY' in license_info:
                    score += 6
                    self.recommendations.append(f"✅ Attribution license promotes reuse: {license_info}")
                else:
                    score += 4
                    self.recommendations.append(f"✅ Open license specified: {license_info}")
            elif license_info and license_info in ['MIT', 'Apache-2.0']:
                score += 5
                self.recommendations.append(f"✅ Permissive license: {license_info}")
            else:
                self.recommendations.append("❌ Use clear open license (CC-BY-4.0, MIT, etc.)")
                
            # Check for usage guidelines
            acknowledgements = metadata.get('Acknowledgements', '')
            if acknowledgements and len(acknowledgements) > 20:
                score += 2
                self.recommendations.append("✅ Usage acknowledgements provided")
            else:
                self.recommendations.append("❌ Add detailed Acknowledgements for proper attribution")
        else:
            license_info = metadata.get('Metadata', {}).get('License', '')
            if license_info.startswith('CC') or 'open' in license_info.lower():
                score += 5
                self.recommendations.append("✅ Open license promotes reuse")
            else:
                self.recommendations.append("❌ Consider more open licensing for better reusability")
        
        # R3: Domain-specific standards and quality
        if is_dataset:
            # Check research domain specification
            domains = metadata.get('ResearchDomains', [])
            if domains and len(domains) >= 1:
                score += 4
                self.recommendations.append(f"✅ Research domains specified: {', '.join(domains[:2])}...")
            else:
                self.recommendations.append("❌ Add ResearchDomains for domain context")
                
            # Check funding information for transparency
            funding = metadata.get('Funding', [])
            if funding:
                score += 3
                self.recommendations.append(f"✅ Funding sources documented ({len(funding)} sources)")
            else:
                self.recommendations.append("❌ Document Funding sources for transparency")
        else:
            study_domain = metadata.get('Categories', {}).get('StudyDomain')
            if study_domain:
                score += 4
                self.recommendations.append(f"✅ Clear domain classification: {study_domain}")
            else:
                self.recommendations.append("❌ Specify StudyDomain for context")
        
        # R4: Quality metrics and ethics
        if is_dataset:
            # Check ethics documentation
            ethics = metadata.get('EthicsApprovals', [])
            if ethics:
                score += 4
                self.recommendations.append(f"✅ Ethics compliance documented ({len(ethics)} approvals)")
            else:
                self.recommendations.append("❌ Document ethics approvals if applicable")
                
            # Check publication readiness
            publications = metadata.get('Publications', [])
            if publications:
                score += 3
                self.recommendations.append(f"✅ Publication context provided ({len(publications)} publications)")
            else:
                self.recommendations.append("❌ Link to related Publications for context")
        else:
            data_quality = metadata.get('Categories', {}).get('DataQuality')
            if data_quality:
                score += 4
                self.recommendations.append(f"✅ Data quality assessed: {data_quality}")
            else:
                self.recommendations.append("❌ Include data quality assessment")
        
        # R5: Versioning and temporal information
        if is_dataset:
            # Check data collection dates
            data_collection = metadata.get('DataCollection', {})
            start_date = data_collection.get('start_date')
            end_date = data_collection.get('end_date')
            
            date_score = 0
            if start_date and re.match(r'^\d{4}-\d{2}-\d{2}$', start_date):
                date_score += 2
                self.recommendations.append("✅ Data collection start date in ISO format")
            else:
                self.recommendations.append("❌ Use ISO date format for DataCollection.start_date")
                
            if end_date and re.match(r'^\d{4}-\d{2}-\d{2}$', end_date):
                date_score += 2
                self.recommendations.append("✅ Data collection end date in ISO format")
            else:
                self.recommendations.append("❌ Use ISO date format for DataCollection.end_date")
                
            score += date_score
        else:
            creation_date = metadata.get('Metadata', {}).get('CreationDate')
            if creation_date and re.match(r'^\d{4}-\d{2}-\d{2}$', creation_date):
                score += 4
                self.recommendations.append("✅ Clear temporal information")
            else:
                self.recommendations.append("❌ Use ISO date format (YYYY-MM-DD)")
        
        return score
    
    def evaluate_dataset(self, metadata_file):
        """Evaluate complete FAIR compliance"""
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            return {"error": f"Could not load metadata: {e}"}
        
        # Get corresponding data file
        data_file = metadata_file.replace('.json', '').replace('_stim', '')
        
        # Run all FAIR checks
        self.score['findable'] = self.check_findable(metadata)
        self.score['accessible'] = self.check_accessible(metadata, data_file)
        self.score['interoperable'] = self.check_interoperable(metadata)
        self.score['reusable'] = self.check_reusable(metadata)
        
        # Calculate percentages
        percentages = {}
        for category, score in self.score.items():
            percentages[category] = (score / self.max_scores[category]) * 100
        
        total_percentage = sum(percentages.values()) / 4
        
        return {
            'scores': self.score,
            'percentages': percentages,
            'total_percentage': total_percentage,
            'recommendations': self.recommendations,
            'grade': self.get_grade(total_percentage)
        }
    
    def get_grade(self, percentage):
        """Convert percentage to letter grade"""
        if percentage >= 90:
            return "A - Excellent FAIR compliance"
        elif percentage >= 80:
            return "B - Good FAIR compliance"
        elif percentage >= 70:
            return "C - Acceptable FAIR compliance"
        elif percentage >= 60:
            return "D - Poor FAIR compliance"
        else:
            return "F - Inadequate FAIR compliance"

def main():
    """Command line FAIR compliance checker"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python fair_checker.py <metadata_file.json>")
        sys.exit(1)
    
    metadata_file = sys.argv[1]
    
    if not os.path.exists(metadata_file):
        print(f"Error: File {metadata_file} not found")
        sys.exit(1)
    
    checker = FAIRComplianceChecker()
    results = checker.evaluate_dataset(metadata_file)
    
    if 'error' in results:
        print(f"❌ {results['error']}")
        sys.exit(1)
    
    # Display results
    print(f"\n🔍 FAIR Compliance Report: {os.path.basename(metadata_file)}")
    print("=" * 60)
    
    # Overall grade
    print(f"🎯 Overall Grade: {results['grade']}")
    print(f"📊 Total Score: {results['total_percentage']:.1f}%\n")
    
    # Individual scores
    print("📈 Category Scores:")
    for category, percentage in results['percentages'].items():
        bar_length = int(percentage / 5)  # Scale to 20 chars max
        bar = "█" * bar_length + "░" * (20 - bar_length)
        print(f"  {category.upper():13} [{bar}] {percentage:5.1f}%")
    
    # Recommendations
    print(f"\n💡 Recommendations ({len(results['recommendations'])} items):")
    for i, rec in enumerate(results['recommendations'], 1):
        print(f"  {i:2d}. {rec}")
    
    # Exit with appropriate code
    sys.exit(0 if results['total_percentage'] >= 70 else 1)

if __name__ == "__main__":
    main()
