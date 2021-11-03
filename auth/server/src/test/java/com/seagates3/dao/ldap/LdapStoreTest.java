import static org.mockito.Matchers.any;

import java.util.HashMap;
import java.util.List;

import org.junit.Assert;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.powermock.api.mockito.PowerMockito;
import org.powermock.core.classloader.annotations.PowerMockIgnore;
import org.powermock.core.classloader.annotations.PrepareForTest;
import org.powermock.modules.junit4.PowerMockRunner;

import com.novell.ldap.LDAPEntry;
import com.seagates3.dao.ldap.LDAPUtils;
import com.seagates3.dao.ldap.LdapStore;
import com.seagates3.model.Account;
import com.seagates3.model.Policy;

@RunWith(PowerMockRunner.class)
    @PrepareForTest({LDAPUtils.class, LdapStore.class})
    @PowerMockIgnore({"javax.management.*"}) public class LdapStoreTest {

 private
  LdapStore ldapstore;
 private
  Policy policy;
 private
  Account account;

  @Before public void setUp() throws Exception {

    account = new Account();
    account.setId("A1234");
    account.setName("account1");

    policy = new Policy();
    policy.setPolicyId("P1234");
    policy.setPath("/");
    policy.setName("policy1");
    policy.setAccount(account);
    policy.setARN("arn:aws:iam::A1234:policy/policy1");
    policy.setCreateDate("2021/12/12 12:23:34");
    policy.setDefaultVersionId("0");
    policy.setAttachmentCount(0);
    policy.setPermissionsBoundaryUsageCount(0);
    policy.setIsPolicyAttachable("true");
    policy.setUpdateDate("2021/12/12 12:23:34");
    policy.setPolicyDoc(
        "{\r\n" + "  \"Id\": \"Policy1632740111416\",\r\n" +
        "  \"Version\": \"2012-10-17\",\r\n" + "  \"Statement\": [\r\n" +
        "    {\r\n" + "      \"Sid\": \"Stmt1632740110513\",\r\n" +
        "      \"Action\": [\r\n" + "        \"s3:PutBucketAcljhghsghsd\"\r\n" +
        "      ],\r\n" + "      \"Effect\": \"Allow\",\r\n" +
        "      \"Resource\": \"arn:aws:s3:::buck1\"\r\n" + "	  \r\n" +
        "    }\r\n" + "\r\n" + "  ]\r\n" + "}");

    ldapstore = new LdapStore();

    PowerMockito.mockStatic(LDAPUtils.class);
  }

  @Test public void testSave() throws Exception {
    PowerMockito.doNothing().when(LDAPUtils.class, "add", any(LDAPEntry.class));
    ldapstore.save(new HashMap(), policy, "Policy");
  }

  @Test public void testFind() throws Exception {
    PowerMockito.when(LDAPUtils.class, "search", any(String.class),
                      any(Integer.class), any(String.class),
                      any(String[].class)).thenReturn(null);
    Policy returnObj = (Policy)ldapstore.find("", policy, "Policy");
    Assert.assertEquals(false, returnObj.exists());
  }

  @Test public void testFindAll() throws Exception {
    PowerMockito.when(LDAPUtils.class, "search", any(String.class),
                      any(Integer.class), any(String.class),
                      any(String[].class)).thenReturn(null);
    List returnObj = ldapstore.findAll("", account, "Policy");
    Assert.assertEquals(true, returnObj.isEmpty());
  }

  @Test public void testDelete() throws Exception {
    PowerMockito.doNothing().when(LDAPUtils.class, "delete", any(String.class));
    ldapstore.delete ("", policy, "Policy");
  }
}
