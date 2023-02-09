#!/bin/sh

while [[ $(nc -z vault 8200; echo $?) -eq 1 ]]; do sleep 1; done

vault login dev-token

vault auth enable approle

vault write auth/approle/role/ekss-role \
    token_policies="ekss-policy" \
    token_ttl=1h \
    token_max_ttl=4h \
    bind_secret_id=true

vault write -f auth/approle/role/ekss-role/role-id role_id="9f03d595-c964-441c-a68e-2e1534f2bb56"
vault write -f auth/approle/role/ekss-role/custom-secret-id secret_id="a3e80b1d-86d3-4c23-85ee-589031ec2cba"

cat <<EOF > /home/vault/ekss-policy.hcl
path "secret/data/ekss/*" {
  capabilities = ["read", "create"]
}
EOF

vault policy write ekss-policy /home/vault/ekss-policy.hcl
