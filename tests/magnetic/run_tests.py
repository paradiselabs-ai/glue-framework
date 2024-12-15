# tests/magnetic/run_tests.py

"""Magnetic System Test Runner

This script runs magnetic system tests and generates detailed reports on:
1. Test coverage
2. Resource cleanup verification
3. State transition analysis
4. Error handling verification
"""

import os
import sys
import pytest
import coverage
from datetime import datetime
from pathlib import Path

class TestMetrics:
    """Track test execution metrics"""
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.cleanup_verified = 0
        self.state_transitions = 0
        self.errors_handled = 0
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """Start test execution"""
        self.start_time = datetime.now()
    
    def finish(self):
        """Finish test execution"""
        self.end_time = datetime.now()
    
    def duration(self):
        """Get test duration"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0
    
    def success_rate(self):
        """Calculate test success rate"""
        if self.total_tests == 0:
            return 0
        return (self.passed_tests / self.total_tests) * 100

class TestReporter:
    """Generate test execution reports"""
    def __init__(self, metrics: TestMetrics):
        self.metrics = metrics
        self.report_dir = Path("test_reports/magnetic")
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(self):
        """Generate test execution report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.report_dir / f"magnetic_test_report_{timestamp}.txt"
        
        with open(report_path, "w") as f:
            f.write("=== Magnetic System Test Report ===\n\n")
            
            # Test Summary
            f.write("Test Summary:\n")
            f.write(f"Total Tests: {self.metrics.total_tests}\n")
            f.write(f"Passed: {self.metrics.passed_tests}\n")
            f.write(f"Failed: {self.metrics.failed_tests}\n")
            f.write(f"Success Rate: {self.metrics.success_rate():.2f}%\n")
            f.write(f"Duration: {self.metrics.duration():.2f} seconds\n\n")
            
            # Verification Metrics
            f.write("Verification Metrics:\n")
            f.write(f"Cleanup Verifications: {self.metrics.cleanup_verified}\n")
            f.write(f"State Transitions: {self.metrics.state_transitions}\n")
            f.write(f"Errors Handled: {self.metrics.errors_handled}\n\n")
            
            # Coverage Summary
            cov = coverage.Coverage()
            cov.load()
            total_coverage = cov.report(file=None)
            f.write(f"Code Coverage: {total_coverage:.2f}%\n\n")
            
            # Recommendations
            f.write("Recommendations:\n")
            if self.metrics.success_rate() < 100:
                f.write("- Fix failing tests\n")
            if total_coverage < 90:
                f.write("- Improve test coverage\n")
            if self.metrics.cleanup_verified < self.metrics.total_tests:
                f.write("- Add cleanup verifications\n")
            if self.metrics.errors_handled < self.metrics.total_tests:
                f.write("- Improve error handling\n")
        
        return report_path

def run_tests():
    """Run magnetic system tests"""
    metrics = TestMetrics()
    metrics.start()
    
    # Start coverage tracking
    cov = coverage.Coverage()
    cov.start()
    
    try:
        # Run tests
        result = pytest.main([
            "tests/magnetic/test_field_core.py",
            "-v",
            "--asyncio-mode=auto"
        ])
        
        # Update metrics
        metrics.total_tests = result.numcollected if hasattr(result, 'numcollected') else 0
        metrics.passed_tests = result.passed if hasattr(result, 'passed') else 0
        metrics.failed_tests = result.failed if hasattr(result, 'failed') else 0
        
        # Stop coverage tracking
        cov.stop()
        cov.save()
        
    finally:
        metrics.finish()
    
    # Generate report
    reporter = TestReporter(metrics)
    report_path = reporter.generate_report()
    print(f"\nTest report generated: {report_path}")
    
    return metrics.success_rate() == 100.0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
