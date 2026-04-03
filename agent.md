# Agent Rules

**Version:** 1.0.0

## Agent Roles

- **Planner**:
  - Responsibilities:
    - Analyze user requirements
    - Create detailed technical specifications
    - Define project structure and architecture
    - Identify dependencies and risks
  - Allowed Providers: openai, claude, gemini
  - Input Requirements: user_requirements, project_context
  - Output Deliverables: technical_plan, architecture_diagram, task_breakdown

- **Coder**:
  - Responsibilities:
    - Implement code based on approved plan
    - Follow coding standards and best practices
    - Write self-documenting code
    - Include error handling
  - Allowed Providers: openai, claude, codex, codellama
  - Input Requirements: approved_plan, specifications
  - Output Deliverables: source_code, code_comments, inline_documentation

- **Reviewer**:
  - Responsibilities:
    - Review code for quality and correctness
    - Check adherence to plan and specifications
    - Identify potential bugs and security issues
    - Suggest improvements and optimizations
  - Allowed Providers: openai, claude, codellama
  - Input Requirements: source_code, technical_plan
  - Output Deliverables: code_review, improvement_suggestions, security_report

- **Tester**:
  - Responsibilities:
    - Generate comprehensive test cases
    - Write unit, integration, and functional tests
    - Ensure code coverage targets are met
    - Validate edge cases
  - Allowed Providers: openai, claude, codex, codellama
  - Input Requirements: source_code, specifications
  - Output Deliverables: test_suites, test_results, coverage_report

- **Debugger**:
  - Responsibilities:
    - Analyze failed tests and errors
    - Identify root causes of issues
    - Implement fixes and validations
    - Verify fixes resolve issues
  - Allowed Providers: openai, claude, codex, codellama
  - Input Requirements: error_logs, failing_tests, source_code
  - Output Deliverables: bug_fixes, root_cause_analysis, prevention_recommendations

## Task Dependencies

- **planning** → **coding** - plan_approved
- **coding** → **reviewing** - code_complete
- **reviewing** → **testing** - review_passed
- **testing** → **debugging** - tests_failed
- **debugging** → **testing** - fixes_applied

## Behavior Guidelines

- Plan approval required before coding (strict)
- Code review required before testing (strict)
- Failed tests trigger debugging (strict)
- Incremental commits (suggested)
- Documentation updates (optional)

## Error Handling

- onFailure: pause
- maxRetries: 3
- retryDelay: 5000ms
- notifyUser: true

## Data Sharing

- **Planner**:
  - Can Read: user_requirements, project_context, existing_docs
  - Can Write: technical_plan, architecture_diagram, task_breakdown
  - Can Modify: project_scope

- **Coder**:
  - Can Read: technical_plan, specifications, existing_code
  - Can Write: source_code, code_comments
  - Can Modify: source_code

- **Reviewer**:
  - Can Read: technical_plan, source_code, specifications
  - Can Write: code_review, improvement_suggestions
  - Can Modify: 

- **Tester**:
  - Can Read: source_code, specifications, technical_plan
  - Can Write: test_suites, test_results
  - Can Modify: test_configuration

- **Debugger**:
  - Can Read: source_code, error_logs, failing_tests, code_review
  - Can Write: bug_fixes, root_cause_analysis
  - Can Modify: source_code

