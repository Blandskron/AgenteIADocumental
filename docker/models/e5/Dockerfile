# Shared build input for both RAG services.
FROM scratch
ARG E5_SOURCE=https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3

ADD --checksum=sha256:987f7a67a38fa564c849bb5d277c52ab9088a84368fc0be31a354125aebb12a0 --chmod=0555 \
    ${E5_SOURCE}/1_Pooling/config.json /model/1_Pooling/config.json
ADD --checksum=sha256:69137736cab8b8903a07fe8afaafdda25aac55415a12a55d1bffa9f581abf959 --chmod=0444 \
    ${E5_SOURCE}/config.json /model/config.json
ADD --checksum=sha256:c6e29747481e8b5dd2b58401966aeac910de39092f90cda9a704b1545f902b04 --chmod=0444 \
    ${E5_SOURCE}/modules.json /model/modules.json
ADD --checksum=sha256:948201d8329907aae938fa62f9ceeed53f5694dacc2b87b9f3b78b37ee986529 --chmod=0444 \
    ${E5_SOURCE}/sentence_bert_config.json /model/sentence_bert_config.json
ADD --checksum=sha256:d05497f1da52c5e09554c0cd874037a083e1dc1b9cfd48034d1c717f1afc07a7 --chmod=0444 \
    ${E5_SOURCE}/special_tokens_map.json /model/special_tokens_map.json
ADD --checksum=sha256:a1d6bc8734a6f635dc158508bef000f8e2e5a759c7d92f984b2c86e5ff53425b --chmod=0444 \
    ${E5_SOURCE}/tokenizer_config.json /model/tokenizer_config.json
ADD --checksum=sha256:0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39 --chmod=0444 \
    ${E5_SOURCE}/tokenizer.json /model/tokenizer.json
ADD --checksum=sha256:cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865 --chmod=0444 \
    ${E5_SOURCE}/sentencepiece.bpe.model /model/sentencepiece.bpe.model
ADD --checksum=sha256:1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477 --chmod=0444 \
    ${E5_SOURCE}/model.safetensors?download=true /model/model.safetensors
ADD --checksum=sha256:0038de97aee16258cecbad7ffda4b4febd6953e747a00e0ddbc8e6ed241e9c1c --chmod=0444 \
    ${E5_SOURCE}/README.md /model/README.md
ADD --checksum=sha256:904dc4d8749877f1dba1cda48200d2462dccbeb7c134d5e4ef6fa75e0198c8fe --chmod=0444 \
    https://raw.githubusercontent.com/microsoft/unilm/31c5b904ca1bf2afb4c234a6675c683a4e5fc7cd/LICENSE /model/LICENSE
