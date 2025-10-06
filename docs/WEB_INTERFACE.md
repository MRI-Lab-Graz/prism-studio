# Web Interface Guide

The Psycho-Validator includes a user-friendly web interface that makes dataset validation accessible to users who prefer not to use the command line.

## Quick Start

### Option 1: Simple Launcher (Recommended)
**Windows users:**
1. Double-click `launch_web.bat`
2. Your browser will open automatically

**Linux/macOS users:**
```bash
python launch_web.py
```

### Option 2: Manual Start
```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Start web interface
python web_interface.py
```

The web interface will open at: http://127.0.0.1:5000

## Features

### 🎯 **User-Friendly Interface**
- Clean, BIDS-validator inspired design
- Drag & drop file upload
- Real-time validation feedback
- No technical knowledge required

### 📁 **Multiple Input Methods**
- **ZIP Upload**: Upload your dataset as a ZIP file
- **Local Folder**: Point to a folder on your computer
- **Drag & Drop**: Simply drag files to the upload area

### 📊 **Comprehensive Results**
- **Visual Dashboard**: Summary cards with statistics
- **Error Categorization**: Organized by error type
- **Warning System**: Non-critical issues highlighted
- **File Listing**: Detailed view of valid/invalid files
- **Downloadable Reports**: JSON export for further analysis

### 🔒 **Privacy & Security**
- **Local Processing**: All validation happens on your computer
- **No Data Upload**: Files never leave your machine
- **Temporary Storage**: Uploaded files are cleaned up automatically

## Interface Overview

### Main Page
- **Upload Section**: Drag & drop or browse for ZIP files
- **Local Folder**: Enter path to existing dataset
- **Dataset Structure Guide**: Visual guide to expected format
- **Feature Overview**: Key capabilities at a glance

### Results Page
- **Summary Statistics**: Total files, valid/invalid counts
- **Overall Status**: Clear VALID/INVALID indicator
- **Dataset Statistics**: Subject/session/modality breakdown
- **Error Details**: Expandable sections with specific issues
- **Action Buttons**: Download report, validate another dataset

## Command Line Options

The web interface supports several configuration options:

```bash
python web_interface.py [options]

Options:
  --host HOST     Host to bind to (default: 127.0.0.1)
  --port PORT     Port number (default: 5000)
  --debug         Enable debug mode
  --public        Allow external connections (host: 0.0.0.0)
```

### Examples
```bash
# Run on different port
python web_interface.py --port 8080

# Allow access from other computers (be careful!)
python web_interface.py --public

# Debug mode for development
python web_interface.py --debug
```

## Troubleshooting

### Web Interface Won't Start
1. **Check Dependencies**: Ensure Flask is installed
   ```bash
   pip install Flask Werkzeug
   ```

2. **Verify Virtual Environment**: Make sure you're in the correct environment
   ```bash
   source .venv/bin/activate
   python -c "import flask; print('Flask installed')"
   ```

3. **Port Conflicts**: Try a different port
   ```bash
   python web_interface.py --port 8080
   ```

### Upload Issues
1. **File Size**: Maximum upload size is 500MB
2. **ZIP Format**: Ensure your dataset is in a proper ZIP file
3. **Browser Compatibility**: Use modern browsers (Chrome, Firefox, Safari, Edge)

### Performance Tips
1. **Large Datasets**: For datasets >100MB, consider using local folder validation
2. **Browser Memory**: Close unused tabs when validating large datasets
3. **Network Drives**: Local folders work better than network drives

## Browser Compatibility

The web interface works with:
- ✅ Chrome 80+
- ✅ Firefox 75+
- ✅ Safari 13+
- ✅ Edge 80+

## Security Considerations

### Local Use (Default)
- Interface only accessible from your computer (127.0.0.1)
- Safe for sensitive research data
- No external network access required

### Public Mode (--public flag)
- ⚠️ **Warning**: Only use on trusted networks
- Makes interface accessible from other computers
- Consider firewall implications
- Not recommended for sensitive data

## Advanced Usage

### API Access
The web interface also provides a simple API for programmatic access:

```bash
# POST validation request
curl -X POST http://127.0.0.1:5000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"dataset_path": "/path/to/dataset"}'
```

### Integration with Scripts
You can start the web interface programmatically:

```python
from web_interface import app
app.run(host='127.0.0.1', port=5000, debug=False)
```

## Comparison with Command Line

| Feature | Web Interface | Command Line |
|---------|---------------|--------------|
| **Ease of Use** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Visual Feedback** | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Automation** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Batch Processing** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Report Export** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Setup Required** | ⭐⭐⭐⭐ | ⭐⭐⭐ |

## Getting Help

1. **Interface Issues**: Check browser console (F12) for errors
2. **Validation Problems**: Use the downloadable JSON report for details
3. **Performance Issues**: Try local folder validation instead of upload
4. **Technical Support**: Include browser type and console errors when reporting issues

The web interface makes the Psycho-Validator accessible to researchers who prefer graphical interfaces while maintaining all the powerful validation capabilities of the command-line tool.