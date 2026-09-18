# Independent coverage review

Use this brief for a fresh, read-only reviewer after writing the bundle. Supply the original confirmed requirements verbatim, the bundle path, and this brief. Keep the generator's plan and audit out of the review brief so their omissions do not become the review's scope. The reviewer owns analysis only; the parent owns all repairs. Use the current model unless the user specifies otherwise.

## Reviewer task

Derive required test cases from the confirmed requirements before reading the generated tests. Do not delegate again. Produce a table with these columns:

```text
Resource | Grant path | Action | Prerequisite or boundary | Required request facts | Expected effect | Existing assertion or gap
```

Expand each grant path separately for every consuming resource and action. A shared condition can be wired correctly for one grant and omitted from another, so coverage for one path does not establish coverage for the others.

For each path, derive an ALLOW case and a DENY case for each independent prerequisite while the other prerequisites remain satisfied. Cover missing required base roles using unrelated roles with matching attributes, tenant isolation, and each relationship or state condition where specified. Keep other grant paths inactive for these negatives. Also derive the required boundary values, optional-attribute defaults, decision-changing overrides, overlapping grants, explicit denials, and default-denied actions. For derived roles, include caller-supplied derived-role names that must not grant access.

Then inspect the policies, tests, and resolved fixtures. Fill the final column only when an assertion exercises the intended resource, action, effect, and prerequisite. Compare actual principal IDs, roles, and resource attributes; labels and test names are not evidence. A negative that fails several prerequisites cannot establish which caused its denial.

Return the complete table, followed by concrete gaps with file references and minimal fixture/test repairs. Report a clean review only when every derived row has supporting evidence. Do not edit files, relax the requirements, or use the generator's pass count as a completeness claim.
