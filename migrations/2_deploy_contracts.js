const PaymentSystem = artifacts.require("PaymentSystem");

module.exports = function (deployer) {
    deployer.deploy(PaymentSystem);
};
