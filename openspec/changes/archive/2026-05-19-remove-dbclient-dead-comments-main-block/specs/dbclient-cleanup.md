# Delta Spec: Remove Dead Code from DBClient

## MODIFIED Requirements

### Requirement: DBClient Source Code Hygiene

`buy/DBClient.py` SHALL contain only active, production-relevant code. All commented-out debug statements, commented-out data transformations, and test/demo blocks MUST be removed.

#### Scenario: Commented-out debug log lines are absent

- **Given** `buy/DBClient.py` source file
- **When** scanning the file for lines containing `# self.log.debug` or `# result = self.__dict_datetime_obj_to_str` or `# [self.__dict_datetime_obj_to_str`
- **Then** zero matches SHALL be found

#### Scenario: No `__main__` test block exists

- **Given** `buy/DBClient.py` source file
- **When** scanning the file for `if __name__ == "__main__"`
- **Then** zero matches SHALL be found

#### Scenario: Active DBClient behavior is unchanged

- **Given** the cleaned `buy/DBClient.py`
- **When** the `DBClient` class is instantiated and its public methods (`select_one`, `select_many`, `select_many_cols`, `execute`, `close`) are called
- **Then** the return values and side effects SHALL be identical to the pre-cleanup version
