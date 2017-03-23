/*
 * COPYRIGHT 2015 SEAGATE LLC
 *
 * THIS DRAWING/DOCUMENT, ITS SPECIFICATIONS, AND THE DATA CONTAINED
 * HEREIN, ARE THE EXCLUSIVE PROPERTY OF SEAGATE TECHNOLOGY
 * LIMITED, ISSUED IN STRICT CONFIDENCE AND SHALL NOT, WITHOUT
 * THE PRIOR WRITTEN PERMISSION OF SEAGATE TECHNOLOGY LIMITED,
 * BE REPRODUCED, COPIED, OR DISCLOSED TO A THIRD PARTY, OR
 * USED FOR ANY PURPOSE WHATSOEVER, OR STORED IN A RETRIEVAL SYSTEM
 * EXCEPT AS ALLOWED BY THE TERMS OF SEAGATE LICENSES AND AGREEMENTS.
 *
 * YOU SHOULD HAVE RECEIVED A COPY OF SEAGATE'S LICENSE ALONG WITH
 * THIS RELEASE. IF NOT PLEASE CONTACT A SEAGATE REPRESENTATIVE
 * http://www.seagate.com/contact
 *
 * Original author:  Kaustubh Deorukhkar   <kaustubh.deorukhkar@seagate.com>
 * Original creation date: 1-Oct-2015
 */

#pragma once

#ifndef __S3_SERVER_S3_PUT_OBJECT_ACTION_H__
#define __S3_SERVER_S3_PUT_OBJECT_ACTION_H__

#include <gtest/gtest_prod.h>
#include <memory>
#include <string>
#include "s3_action_base.h"
#include "s3_async_buffer.h"
#include "s3_bucket_metadata.h"
#include "s3_clovis_writer.h"
#include "s3_factory.h"
#include "s3_object_metadata.h"
#include "s3_timer.h"

class S3PutObjectAction : public S3Action {
  struct m0_uint128 old_object_oid;
  struct m0_uint128 new_object_oid;
  struct m0_uint128 object_list_oid;
  // Maximum retry count for collision resolution
  unsigned short tried_count;
  // string used for salting the uri
  std::string salt;
  std::shared_ptr<S3BucketMetadata> bucket_metadata;
  std::shared_ptr<S3ObjectMetadata> object_metadata;
  std::shared_ptr<S3ClovisWriter> clovis_writer;

  size_t total_data_to_stream;
  S3Timer create_object_timer;
  S3Timer write_content_timer;
  bool write_in_progress;

  std::shared_ptr<S3BucketMetadataFactory> bucket_metadata_factory;
  std::shared_ptr<S3ObjectMetadataFactory> object_metadata_factory;
  std::shared_ptr<S3ClovisWriterFactory> clovis_writer_factory;

 public:
  S3PutObjectAction(std::shared_ptr<S3RequestObject> req,
                    S3BucketMetadataFactory* bucket_meta_factory = NULL,
                    S3ObjectMetadataFactory* object_meta_factory = NULL,
                    S3ClovisWriterFactory* clovis_s3_factory = NULL);

  void setup_steps();
  // void start();

  void fetch_bucket_info();
  void fetch_object_info();
  void fetch_object_info_status();
  void create_object();
  void create_object_failed();
  void create_new_oid(struct m0_uint128 current_oid);
  void collision_detected();

  void initiate_data_streaming();
  void consume_incoming_content();
  void write_object(std::shared_ptr<S3AsyncBufferOptContainer> buffer);

  void write_object_successful();
  void write_object_failed();
  void save_metadata();
  void delete_old_object_if_present();
  void delete_old_object_failed();
  void send_response_to_s3_client();

  // rollback functions
  void rollback_create();
  void rollback_create_failed();

  FRIEND_TEST(S3PutObjectActionTest, ConstructorTest);
  FRIEND_TEST(S3PutObjectActionTest, FetchBucketInfo);
  FRIEND_TEST(S3PutObjectActionTest, FetchObjectInfoWhenBucketNotPresent);
  FRIEND_TEST(S3PutObjectActionTest,
              FetchObjectInfoWhenBucketAndObjIndexPresent);
  FRIEND_TEST(S3PutObjectActionTest,
              FetchObjectInfoWhenBucketPresentAndObjIndexAbsent);
  FRIEND_TEST(S3PutObjectActionTest,
              FetchObjectInfoReturnedFoundShouldHaveNewOID);
  FRIEND_TEST(S3PutObjectActionTest,
              FetchObjectInfoReturnedNotFoundShouldUseURL2OID);
  FRIEND_TEST(S3PutObjectActionTest,
              FetchObjectInfoReturnedInvalidStateReportsError);
  FRIEND_TEST(S3PutObjectActionTest, CreateObjectFirstAttempt);
  FRIEND_TEST(S3PutObjectActionTest, CreateObjectSecondAttempt);
  FRIEND_TEST(S3PutObjectActionTest, CreateObjectFailedTestWhileShutdown);
  FRIEND_TEST(S3PutObjectActionTest,
              CreateObjectFailedWithCollisionExceededRetry);
  FRIEND_TEST(S3PutObjectActionTest, CreateObjectFailedWithCollisionRetry);
  FRIEND_TEST(S3PutObjectActionTest, CreateObjectFailedTest);
  FRIEND_TEST(S3PutObjectActionTest, RollbackTest);
  FRIEND_TEST(S3PutObjectActionTest, CreateNewOidTest);
  FRIEND_TEST(S3PutObjectActionTest, RollbackFailedTest1);
  FRIEND_TEST(S3PutObjectActionTest, RollbackFailedTest2);
  FRIEND_TEST(S3PutObjectActionTest, InitiateDataStreamingForZeroSizeObject);
  FRIEND_TEST(S3PutObjectActionTest, InitiateDataStreamingExpectingMoreData);
  FRIEND_TEST(S3PutObjectActionTest, InitiateDataStreamingWeHaveAllData);
  FRIEND_TEST(S3PutObjectActionTest, ConsumeIncomingShouldWriteIfWeAllData);
  FRIEND_TEST(S3PutObjectActionTest, ConsumeIncomingShouldWriteIfWeExactData);
  FRIEND_TEST(S3PutObjectActionTest,
              ConsumeIncomingShouldWriteIfWeHaveMoreData);
  FRIEND_TEST(S3PutObjectActionTest,
              ConsumeIncomingShouldPauseWhenWeHaveTooMuch);
  FRIEND_TEST(S3PutObjectActionTest,
              ConsumeIncomingShouldNotWriteWhenWriteInprogress);
  FRIEND_TEST(S3PutObjectActionTest,
              WriteObjectShouldWriteContentAndMarkProgress);
  FRIEND_TEST(S3PutObjectActionTest, WriteObjectFailedShouldUndoMarkProgress);
  FRIEND_TEST(S3PutObjectActionTest, WriteObjectSuccessfulWhileShuttingDown);
  FRIEND_TEST(S3PutObjectActionTest,
              WriteObjectSuccessfulWhileShuttingDownAndRollback);
  FRIEND_TEST(S3PutObjectActionTest,
              WriteObjectSuccessfulShouldWriteStateAllData);
  FRIEND_TEST(S3PutObjectActionTest,
              WriteObjectSuccessfulShouldWriteWhenExactWritableSize);
  FRIEND_TEST(S3PutObjectActionTest,
              WriteObjectSuccessfulShouldWriteSomeDataWhenMoreData);
  FRIEND_TEST(S3PutObjectActionTest,
              WriteObjectSuccessfulDoNextStepWhenAllIsWritten);
  FRIEND_TEST(S3PutObjectActionTest,
              WriteObjectSuccessfulShouldRestartReadingData);
  FRIEND_TEST(S3PutObjectActionTest, SaveMetadata);
  FRIEND_TEST(S3PutObjectActionTest, DeleteObjectNotRequired);
  FRIEND_TEST(S3PutObjectActionTest, DeleteObjectSinceItsPresent);
  FRIEND_TEST(S3PutObjectActionTest, DeleteObjectFailed);
  FRIEND_TEST(S3PutObjectActionTest, SendResponseWhenShuttingDown);
  FRIEND_TEST(S3PutObjectActionTest, SendErrorResponse);
  FRIEND_TEST(S3PutObjectActionTest, SendSuccessResponse);
  FRIEND_TEST(S3PutObjectActionTest, SendFailedResponse);
};

#endif
