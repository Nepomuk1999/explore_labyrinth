#!/usr/bin/env python

import os
import sys
import time
import traceback
import actionlib
import matplotlib.pyplot as plt
import numpy as np
import rospy
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from nav_msgs.msg import OccupancyGrid
from nav_msgs.msg import Odometry

if os.name == 'nt':
    pass
else:
    import termios

GOAL_MIN_DIST_TO_WALL = 5


# Publisher
class LabyrinthExplorer:

    def __init__(self):
        self._pub = Publisher('/explorer_goal_pos', MoveBaseGoal, queue_size=10)

        print "init Movement Controller"
        self.map_trimmer = MapTrimmer()
        self._occupancy_grid = rospy.wait_for_message('/map', OccupancyGrid)
        self._occupancy_map = self._occupancy_grid.data
        self._offset_x = self._occupancy_grid.info.origin.position.x
        self._offset_y = self._occupancy_grid.info.origin.position.y
        self._resolution = self._occupancy_grid.info.resolution
        self._map_height = self._occupancy_grid.info.height
        self._map_width = self._occupancy_grid.info.width
        # reshape map
        trimmed_map = np.array(self._occupancy_map)
        self._occupancy_map  = trimmed_map.reshape((self._map_width, self._map_height))

        self._odom_sub = rospy.Subscriber('/odom', Odometry, self.pose_callback)
        self._current_pose = None
        self._current_x = None
        self._current_y = None
        while self._current_pose is None:
            time.sleep(2)
        self._client = actionlib.SimpleActionClient('/move_base', MoveBaseAction)
        self._client.wait_for_server()

        self._start_x, self._start_y = self.transform_to_pos(self._current_pose.position.x, self._current_pose.position.y)
        self.movementcontroller()

    def pose_callback(self, msg):
        self._current_pose = msg.pose.pose
        self._current_x = self._current_pose.position.x
        self._current_y = self._current_pose.position.y

        self._current_y, self._current_x = self.transform_to_pos(self._current_x, self._current_y)
        # print msg.pose.pose

    def transform_to_pos(self, m_x, m_y):
        pos_x = np.int((m_x - self._offset_x) / self._resolution)
        pos_y = np.int((m_y - self._offset_y) / self._resolution)
        return pos_x, pos_y

    def transform_to_meter(self, pos_x, pos_y):
        m_x = pos_x * self._resolution + self._offset_x
        m_y = pos_y * self._resolution + self._offset_y
        return m_x, m_y

    def bfs(self, current_map, robot_pos_x, robot_pos_y, last_x, last_y):
        if robot_pos_x == self._start_x and robot_pos_y == self._start_y:
            robot_pos_y = robot_pos_y + 2
        print 'bfs started'
        start_pose = np.array([robot_pos_x, robot_pos_y])
        path = [start_pose]

        map_size_y, map_size_x = np.shape(current_map)
        closed_list = []

        # Plot heatmap of trimmed map
        # current_map[robot_pos_y, robot_pos_x] = 4
        # plt.imshow(current_map, cmap='hot', interpolation='nearest')
        # plt.show()
        depth_counter = 0
        last_x_known = 0
        last_y_known = 0
        while len(path) > 0:
            current_path = path.pop(0)
            closed_list.append(current_path)
            current_x = current_path[0]
            current_y = current_path[1]

            # save last known cell
            if current_map[current_y, current_x] == 0:
                last_x_known = current_x
                last_y_known = current_y

            # is wall or already visited skip
            if current_map[current_y, current_x] == 1:
                continue
            # unknown cell found
            if current_map[current_y, current_x] == -1:
                return self.next_known_cell(current_x, current_y, current_map)

            # add all neighbours of current cell
            directions = np.array([[current_x - 1, current_y], [current_x + 1, current_y],
                                   [current_x, current_y - 1], [current_x, current_y + 1]])
            np.random.shuffle(directions)
            for i in directions:
                if not self.cointains_pos(i, closed_list):
                    if not self.cointains_pos(i, path):
                        path.append(i)
            depth_counter = depth_counter + 1
        return self._start_x, self._start_y

    def cointains_pos(self, array, array_array):
        for i in array_array:
            if i[0] == array[0]:
                if i[1] == array[1]:
                    return True
        return False

    def next_known_cell(self, pos_x, pos_y, current_map):
        start_pose = np.array([pos_x, pos_y])
        path = [start_pose]
        closed_list = []
        while len(path) > 0:
            current_path = path.pop(0)
            closed_list.append(current_path)
            current_x = current_path[0]
            current_y = current_path[1]
            # is wall or already visited skip
            if current_map[current_y, current_x] == 1:
                continue
            # unknown cell found
            if current_map[current_y, current_x] == 0:
                return self.goal_pos_correction(current_y, current_x, current_map)
            # add all neighbours of current cell
            directions = np.array([[current_x - 1, current_y], [current_x + 1, current_y],
                                   [current_x, current_y - 1], [current_x, current_y + 1]])
            np.random.shuffle(directions)
            for i in directions:
                if not self.cointains_pos(i, closed_list):
                    if not self.cointains_pos(i, path):
                        path.append(i)

    def goal_pos_correction(self, pos_x, pos_y, current_map):
        i = 1
        j = 0
        print 'goal pos corr st'
        current_blob = current_map[[]]
        return pos_x, pos_y

    def update_map_data(self, occupancy_grid):
        self._occupancy_map = occupancy_grid.data
        meta_data = occupancy_grid.info
        self._offset_x = meta_data.origin.position.x
        self._offset_y = meta_data.origin.position.y
        self._resolution = meta_data.resolution
        self._map_height = meta_data.height
        self._map_width = meta_data.width
        # reshape map
        trimmed_map = np.array(self._occupancy_map)
        self._occupancy_map  = trimmed_map.reshape((self._map_width, self._map_height))

    def movementcontroller(self):
        print "movementcontroller()"
        status = 'mapping'
        next_x = -1
        next_y = -1
        while not rospy.is_shutdown():
                # get map to avoid update while processing
                self._occupancy_grid = rospy.wait_for_message("/map", OccupancyGrid)
                self.update_map_data(self._occupancy_grid)
                cleared_map = self.map_trimmer.trim_map(self._occupancy_map)

                next_x, next_y = self.bfs(cleared_map, self._current_x, self._current_y, next_x, next_y)
                next_x, next_y = self.transform_to_meter(next_x, next_y)

                # Plot heatmap of trimmed map
                #plt.imshow(cleared_map, cmap='hot', interpolation='nearest')
                #plt.show()
                self.publish_goal(next_x, next_y)

    def publish_goal(self, x_goal, y_goal):
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = x_goal
        goal.target_pose.pose.position.y = y_goal
        goal.target_pose.pose.orientation.w = 1
        self._pub.publish(goal)


class MapTrimmer:

    def __init__(self):
        pass

    def trim_map(self, untrimmed_map):

        # set values of 100 to 1 for walls
        untrimmed_map[untrimmed_map == 100] = 1

        # plt.imshow(trimmed_map, cmap='hot', interpolation='nearest')
        # plt.show()

        # inflate walls
        trimmed_map = self.inflate_wals(untrimmed_map, 0)

        # # Plot heatmap of trimmed map
        # plt.imshow(trimmed_map, cmap='hot', interpolation='nearest')
        # plt.show()
        # time.sleep(2)

        return trimmed_map

    def inflate_wals(self, trimmed_map, inflation_factor):
        to_be_inflated = np.where(trimmed_map == 5)
        map_size_y, map_size_x = trimmed_map.shape
        x_list = to_be_inflated[1]
        y_list = to_be_inflated[0]
        for i in range(0, len(x_list)):
            x = x_list[i]
            y = y_list[i]
            for j in range(0 - inflation_factor, inflation_factor + 1):
                for k in range(0 - inflation_factor, inflation_factor + 1):
                    if 0 < x + j < map_size_x - 1 and 0 < y + k < map_size_y - 1:
                        trimmed_map[y+k][x+j] = 1
        return trimmed_map


def main():
    if os.name != 'nt':
        settings = termios.tcgetattr(sys.stdin)
    rospy.init_node('explore_labyrinth')
    try:
        LabyrinthExplorer()
    except Exception as e:
        print e
        traceback.print_exc()


if __name__ == "__main__":
    main()