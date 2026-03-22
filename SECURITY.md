# Security Policy

## Reporting a Vulnerability

We take the security of TG WS Proxy seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### How to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report vulnerabilities via:
- **Email**: maksimqwe42@mail.ru
- **GitHub Security Advisories**: Use the "Report a vulnerability" feature

Please include the following information:
- Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the issue
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### Response Time

We will acknowledge receipt of your report within **48 hours** and send you a more detailed response within **5 days** indicating the next steps.

After the initial reply, we will keep you informed of the progress toward a fix and announcement.

## Security Best Practices

### For Users

1. **Keep dependencies updated**: Regularly run `pip install --upgrade -r requirements.txt`
2. **Run security audits**: Use the provided security audit script
3. **Monitor logs**: Watch for unusual connection patterns
4. **Use rate limiting**: Enable rate limiting to prevent abuse
5. **Restrict access**: Use IP whitelist/blacklist when possible

### For Developers

1. **Run security checks before committing**:
   ```bash
   python scripts/security_audit.py
   ```

2. **Keep dependencies secure**:
   ```bash
   pip-audit -r requirements.txt
   safety check
   ```

3. **Follow secure coding practices**:
   - Validate all user input
   - Use parameterized queries (where applicable)
   - Implement proper error handling
   - Log security-relevant events

## Automated Security Scanning

### CI/CD Integration

Our GitHub Actions workflow automatically runs security scans on every push and pull request:

- **pip-audit**: Scans dependencies for known vulnerabilities
- **safety**: Additional vulnerability checking
- **JSON report**: Generated and uploaded as artifact (30-day retention)

### Local Security Audit

Run the security audit script:

```bash
# Check all requirements files
python scripts/security_audit.py

# Check specific file
python scripts/security_audit.py requirements.txt

# Generate report
python scripts/security_audit.py requirements.txt requirements-dev.txt
```

### Manual Security Checks

```bash
# Install security tools
pip install pip-audit safety

# Run pip-audit
pip-audit -r requirements.txt --desc

# Run safety
safety check -r requirements.txt

# Generate detailed report
pip-audit -r requirements.txt -f json > security-report.json
```

## Security Features

### Rate Limiting

- Per-IP rate limiting (configurable)
- Token bucket algorithm for efficiency
- DDoS protection with automatic banning
- Connection flood detection
- Geographic rate limiting (/24 subnet)

### Connection Security

- SOCKS5 authentication support
- WebSocket secure handshake
- TLS/SSL for WebSocket connections
- Connection pooling with health checks
- Circuit breaker for cascade failure protection

### Monitoring & Alerting

- Real-time connection monitoring
- Suspicious activity scoring
- Automatic ban on threshold exceed
- Prometheus metrics export
- Security event logging

## Dependency Management

### Current Dependencies

All dependencies are pinned to specific versions in `requirements.txt` for reproducibility.

### Update Policy

- **Major updates**: Tested thoroughly before merging
- **Minor updates**: Quick security patches
- **Patch updates**: Applied automatically by Dependabot

### Known Vulnerabilities

We maintain a zero-tolerance policy for known vulnerabilities in production dependencies. Any reported vulnerabilities are addressed within:
- **Critical**: 24 hours
- **High**: 7 days
- **Medium**: 30 days
- **Low**: Next release cycle

## Security Checklist

Before each release, verify:

- [ ] All dependencies are up to date
- [ ] No known vulnerabilities in dependencies
- [ ] Security audit passes (`python scripts/security_audit.py`)
- [ ] Rate limiting is enabled and configured
- [ ] Logging captures security events
- [ ] No sensitive data in logs
- [ ] All tests pass
- [ ] Code review completed

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://docs.python.org/3/library/security.html)
- [pip-audit Documentation](https://pypi.org/project/pip-audit/)
- [Safety Documentation](https://pyup.io/safety/)

---

**Last Updated**: 2026-03-23  
**Version**: 1.0
