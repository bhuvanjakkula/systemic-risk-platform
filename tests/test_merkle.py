import hashlib
import unittest

from src.transparency.merkle import leaf_hash, merkle_root, merkle_proof, verify_proof


class MerkleTests(unittest.TestCase):
    def test_empty_and_single_leaf(self):
        self.assertEqual(merkle_root([]), hashlib.sha256(b'empty').digest())
        leaf = leaf_hash('single')
        self.assertEqual(merkle_root([leaf]), leaf)
        self.assertEqual(merkle_proof([leaf], 0), [])
        self.assertTrue(verify_proof(leaf, [], leaf))

    def test_all_positions_and_input_preservation(self):
        for count in (2, 3, 5, 8, 17):
            leaves = [leaf_hash(str(i)) for i in range(count)]
            before = leaves[:]
            root = merkle_root(leaves)
            for index, leaf in enumerate(leaves):
                with self.subTest(count=count, index=index):
                    self.assertTrue(verify_proof(leaf, merkle_proof(leaves, index), root))
            self.assertEqual(leaves, before)

    def test_tampering(self):
        leaves = [leaf_hash('a'), leaf_hash('b'), leaf_hash('c')]
        root = merkle_root(leaves)
        proof = merkle_proof(leaves, 0)
        self.assertFalse(verify_proof(leaf_hash('tampered'), proof, root))
        self.assertFalse(verify_proof(leaves[0], proof, bytes(32)))
        sibling, side = proof[0]
        modified = [(bytes(32), side)] + proof[1:]
        self.assertFalse(verify_proof(leaves[0], modified, root))
        modified = [(sibling, 'left')] + proof[1:]
        self.assertFalse(verify_proof(leaves[0], modified, root))


if __name__ == '__main__':
    unittest.main()
