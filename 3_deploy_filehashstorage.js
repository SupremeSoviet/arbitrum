const FileHashStorage = artifacts.require("FileHashStorage");

module.exports = function(deployer) {
    deployer.deploy(FileHashStorage);
};
