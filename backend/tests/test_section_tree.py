import pytest
from pathlib import Path
from app.ingestion.section_tree import extract_section_tree

def test_extract_section_tree_with_real_markdown():
    fixture_path = Path(__file__).parent.parent / "app" / "ingestion" / "tests" / "fixtures" / "docling_output" / "PG Fee Structure 2025-26.md"
    if fixture_path.exists():
        markdown_text = fixture_path.read_text(encoding="utf-8")
    else:
        markdown_text = """# 1. TUITION AND ACADEMIC FEES
Details of tuition fee structure.
## 1.1 Semester Fees
Fee components per semester.
### 1.1.1 Laboratory Charges
Special lab fees.
## 1.2 Examination Fees
Assessment and exam charges.
# 2. HOSTEL AND MESS CHARGES
Hostel room allotment rules.
## 2.1 Room Rent
Single and shared occupancy charges.
"""
    
    # Extract the tree
    tree = extract_section_tree(markdown_text)
    
    # Basic assertions
    assert isinstance(tree, list)
    assert len(tree) > 0
    
    # Print the tree for debugging purposes to see what it looks like
    # We can inspect the first root node
    first_root = tree[0]
    assert "title" in first_root
    assert "section_path" in first_root
    assert "children" in first_root
    
    # Let's verify a known heading from the PG Fee Structure
    # Example: "2. HOSTEL FEE" or similar might be in there. We just verify the structure is sound.
    # Check that children have parent paths
    def verify_paths(node, parent_path=""):
        if parent_path:
            assert node["section_path"].startswith(parent_path)
            assert node["section_path"].endswith(node["title"])
            assert node["section_path"] == f"{parent_path} / {node['title']}"
        else:
            assert node["section_path"] == node["title"]
            
        for child in node["children"]:
            verify_paths(child, node["section_path"])
            
    for node in tree:
        verify_paths(node)

def test_extract_section_tree_simple():
    markdown = """
# Heading 1
Some text
## Heading 1.1
More text
### Heading 1.1.1
Even more
## Heading 1.2
Text
# Heading 2
Text
"""
    tree = extract_section_tree(markdown)
    assert len(tree) == 2
    assert tree[0]["title"] == "Heading 1"
    assert tree[0]["section_path"] == "Heading 1"
    assert len(tree[0]["children"]) == 2
    
    child1 = tree[0]["children"][0]
    assert child1["title"] == "Heading 1.1"
    assert child1["section_path"] == "Heading 1 / Heading 1.1"
    assert len(child1["children"]) == 1
    
    grandchild = child1["children"][0]
    assert grandchild["title"] == "Heading 1.1.1"
    assert grandchild["section_path"] == "Heading 1 / Heading 1.1 / Heading 1.1.1"
    
    child2 = tree[0]["children"][1]
    assert child2["title"] == "Heading 1.2"
    assert child2["section_path"] == "Heading 1 / Heading 1.2"
    
    assert tree[1]["title"] == "Heading 2"
    assert tree[1]["section_path"] == "Heading 2"
    assert len(tree[1]["children"]) == 0
