// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract FileHashStorage {
    mapping(string => bytes32) private fileHashes;

    function storeFileHash(string memory fileID, bytes32 fileHash) public {
        fileHashes[fileID] = fileHash;
    }

    function verifyFileHash(string memory fileID, bytes32 fileHash) public view returns (bool) {
        return fileHashes[fileID] == fileHash;
    }
}
